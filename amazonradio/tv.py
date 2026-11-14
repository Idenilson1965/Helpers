#!/usr/bin/env python3
"""TV via playlists do YouTube: mapeia programas e monitora citações de clientes.

  python tv.py map            # gera programas_tv.xlsx (programa, emissora, dias, horário, última publicação, DESATUALIZADA)
  python tv.py watch          # loop: 1h após cada vídeo novo -> transcreve -> acha clientes -> corta a matéria -> sobe
  python tv.py once           # uma varredura só (para cron)
Usa yt-dlp (precisa de acesso ao YouTube) e o mesmo Whisper/clientes do radio.py.
"""
import csv, json, os, re, statistics, subprocess, sys, time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import radio
from radio import DATA, HERE, TZ

STALE_DAYS = 60
SAMPLE = int(os.environ.get("TV_SAMPLE", 30))          # vídeos recentes analisados por playlist
DELAY_MIN = int(os.environ.get("TV_DELAY_MIN", 60))    # espera após a publicação (30–120)
MAX_AGE_H = int(os.environ.get("TV_MAX_AGE_H", 48))    # ignora vídeos mais velhos que isso no watch
UPLOAD_CMD = os.environ.get("AMAZONCLIP_UPLOAD_CMD", "")  # ex.: 'python upload.py {file}'
TV = DATA / "tv"


def playlists():
    return list(csv.DictReader(open(HERE / "tv_playlists.csv", encoding="utf-8")))


def fetch(pid, n):
    """Últimos n vídeos: [{id,title,ts(epoch),live}]"""
    cmd = ["yt-dlp", "--ignore-errors", "--skip-download", "--playlist-end", str(n),
           "--print", "%(id)s\t%(title)s\t%(release_timestamp)s\t%(timestamp)s\t%(live_status)s",
           f"https://www.youtube.com/playlist?list={pid}"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    vids = []
    for ln in out.splitlines():
        p = ln.split("\t")
        if len(p) < 5: continue
        ts = next((float(x) for x in (p[2], p[3]) if x not in ("NA", "None", "")), None)
        if ts: vids.append({"id": p[0], "title": p[1], "ts": ts, "live": p[4]})
    return vids


# ---------------------------------------------------------------- planilha
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def summarize(vids, now=None):
    """Dias e horário típicos (do horário de publicação, fuso Manaus) + status de atualização."""
    now = now or datetime.now(TZ)
    if not vids:
        return {"dias": "", "horario": "", "faixa": "", "ultimo": "", "n": 0, "status": "SEM VÍDEOS / ERRO"}
    dts = [datetime.fromtimestamp(v["ts"], TZ) for v in vids]
    cnt = Counter(d.weekday() for d in dts)
    top = max(cnt.values())
    days = sorted(k for k, c in cnt.items() if c >= 0.4 * top)
    sel = [d for d in dts if d.weekday() in days]
    mins = sorted(d.hour * 60 + d.minute for d in sel)
    med = int(statistics.median(mins))
    lo, hi = mins[len(mins) // 10], mins[-1 - len(mins) // 10]
    f = lambda m: f"{m // 60:02d}:{m % 60:02d}"
    last = max(dts)
    stale = (now - last).days > STALE_DAYS
    return {"dias": ", ".join(DIAS[d] for d in days), "horario": f(med), "faixa": f"{f(lo)}–{f(hi)}",
            "ultimo": f"{last:%Y-%m-%d}", "n": len(vids),
            "status": f"DESATUALIZADA ({(now - last).days} dias sem vídeo)" if stale else "ativa"}


def cmd_map(_):
    rows = []
    for p in playlists():
        s = summarize(fetch(p["playlist_id"], SAMPLE)) if p["processar"] == "sim" else \
            {"dias": "", "horario": "", "faixa": "", "ultimo": "", "n": 0, "status": "ignorada"}
        print(p["emissora"], "|", p["programa"], "|", s["status"])
        rows.append({"Programa": p["programa"], "Emissora": p["emissora"], "Dia(s) veiculado": s["dias"],
                     "Horário (publicação, Manaus)": s["horario"], "Faixa típica": s["faixa"],
                     "Último vídeo": s["ultimo"], "Vídeos analisados": s["n"], "Status": s["status"],
                     "Observação": p["observacao"], "Playlist": f"https://www.youtube.com/playlist?list={p['playlist_id']}"})
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Programas TV"
    ws.append(list(rows[0]))
    for c in ws[1]: c.font = Font(bold=True)
    red = PatternFill("solid", fgColor="F8CBAD")
    for r in rows:
        ws.append(list(r.values()))
        if r["Status"].startswith(("DESATUALIZADA", "SEM")):
            for c in ws[ws.max_row]: c.fill = red
    for col, w in zip("ABCDEFGHIJ", (28, 18, 22, 16, 14, 13, 10, 34, 40, 60)): ws.column_dimensions[col].width = w
    out = HERE / "programas_tv.xlsx"; wb.save(out); print("salvo", out)


# ---------------------------------------------------------------- monitor
def seen():
    f = TV / "seen.json"
    return json.loads(f.read_text()) if f.exists() else {}


def save_seen(s):
    TV.mkdir(parents=True, exist_ok=True); (TV / "seen.json").write_text(json.dumps(s))


def process(p, v):
    """Baixa só o áudio, transcreve, procura clientes; se achar, baixa só o trecho da matéria em vídeo."""
    TV.mkdir(parents=True, exist_ok=True)
    a = TV / f"{v['id']}.mp3"
    subprocess.run(["yt-dlp", "-q", "-x", "--audio-format", "mp3", "--postprocessor-args", "-ac 1 -ar 22050 -b:a 32k",
                    "-o", str(TV / f"{v['id']}.%(ext)s"), f"https://www.youtube.com/watch?v={v['id']}"], check=True)
    segs, _ = radio.pick_asr()(a)
    (TV / f"{v['id']}.json").write_text(json.dumps(segs, ensure_ascii=False))
    use_llm = (os.environ.get("RADIO_LLM") == "ollama" or os.environ.get("OPENAI_API_KEY")) and os.environ.get("RADIO_BOUNDS") != "gap"
    clips = {}
    for cli, termo, i, j in radio.find_hits(segs):
        x, y = radio.bounds_llm(segs, i, j, termo) if use_llm else radio.bounds_gap(segs, i, j)
        for (c2, a2, b2), val in list(clips.items()):
            if c2 == cli and x <= b2 and a2 <= y:
                del clips[(c2, a2, b2)]; x, y = min(x, a2), max(y, b2); val["t"].add(termo); break
        else:
            val = {"t": {termo}}
        clips[(cli, x, y)] = val
    new = []
    for (cli, x, y), val in clips.items():
        t0, t1 = max(0, segs[x]["start"] - radio.PAD_CLIP[0]), segs[y]["end"] + radio.PAD_CLIP[1]
        d = TV / "clips" / re.sub(r"\W+", "_", radio.fold(cli)); d.mkdir(parents=True, exist_ok=True)
        f = d / f"{v['id']}_{int(t0)}.mp4"
        if not f.exists():  # só o trecho, cortado no quadro certo
            subprocess.run(["yt-dlp", "-q", "-f", "bv*[height<=720]+ba/b[height<=720]", "--merge-output-format", "mp4",
                            "--download-sections", f"*{t0:.1f}-{t1:.1f}", "--force-keyframes-at-cuts",
                            "-o", str(f), f"https://www.youtube.com/watch?v={v['id']}"], check=True)
        pub = datetime.fromtimestamp(v["ts"], TZ)
        new.append({"publicado": f"{pub:%Y-%m-%d %H:%M}", "cliente": cli, "termos": "; ".join(sorted(val["t"])),
                    "emissora": p["emissora"], "programa": p["programa"], "titulo_video": v["title"],
                    "url": f"https://www.youtube.com/watch?v={v['id']}&t={int(t0)}s", "duracao_s": round(t1 - t0, 1),
                    "arquivo": str(f), "texto": " ".join(s["text"] for s in segs[x:y + 1])})
        if UPLOAD_CMD:
            subprocess.run(UPLOAD_CMD.format(file=f), shell=True)
    if new:
        log = TV / "clips_tv.csv"; first = not log.exists()
        with open(log, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(new[0])); first and w.writeheader(); w.writerows(new)
    a.unlink(missing_ok=True)  # áudio bruto não é mais necessário
    return new


def scan():
    s, now = seen(), time.time()
    for p in playlists():
        if p["processar"] != "sim": continue
        for v in fetch(p["playlist_id"], 10):
            age = now - v["ts"]
            if v["id"] in s or v["live"] in ("is_live", "is_upcoming") or age < DELAY_MIN * 60 or age > MAX_AGE_H * 3600:
                continue
            print(f"{p['programa']}: {v['title']}")
            try:
                for c in process(p, v): print("  CLIPE", c["cliente"], c["arquivo"])
                s[v["id"]] = int(now)
            except Exception as e:
                print("  erro:", e)
            save_seen(s)


def main():
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    if c == "map": cmd_map(None)
    elif c == "once": scan()
    elif c == "watch":
        while True: scan(); time.sleep(600)
    else: sys.exit(__doc__)


if __name__ == "__main__":
    main()
