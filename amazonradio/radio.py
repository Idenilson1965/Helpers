#!/usr/bin/env python3
"""AmazonRadio: captura streams nos horários dos programas, transcreve,
acha menções a clientes e corta a matéria exata.

  python radio.py plan                 # o que será gravado hoje
  python radio.py daemon               # grava + transcreve + corta, automático
  python radio.py record  ID HH:MM HH:MM   # gravação manual
  python radio.py transcribe [ARQ...]  # transcreve o que falta
  python radio.py cut [ARQ.json...]    # (re)corta clipes dos clientes
"""
import csv, json, os, platform, re, subprocess, sys, tempfile, threading, time, unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

HERE = Path(__file__).parent
DATA = Path(os.environ.get("RADIO_DATA", HERE / "data"))
TZ = ZoneInfo("America/Manaus")
CHUNK = 900            # s por pedaço enviado ao Whisper (API)
KBPS = int(os.environ.get("RADIO_KBPS", 32))  # 32k mono = 14,4 MB/h (fala fica ok)
KEEP_DAYS = int(os.environ.get("RADIO_KEEP_DAYS", 3))  # apaga áudio bruto mais velho (clipes ficam)
PAD_REC = 30           # s extras gravados antes/depois da janela
PAD_CLIP = (0.5, 0.8)  # s de folga no início/fim do clipe
MAX_SIDE = 150         # s máx. procurados para cada lado da menção
GAP = 1.6              # s de silêncio que separa matérias (heurística sem IA)


def rows(name):
    with open(HERE / name, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def stations():
    return {r["station_id"]: r for r in rows("stations.csv")}


def fold(s):  # minúscula sem acento, preservando o comprimento
    return "".join(unicodedata.normalize("NFD", c)[0] for c in s).lower()


def hm(date, s):
    h, m = map(int, s.split(":"))
    return datetime(date.year, date.month, date.day, h, m, tzinfo=TZ)


# ---------------------------------------------------------------- agenda
def windows(date):
    """Janelas por emissora, com programas contíguos fundidos."""
    by = {}
    for r in rows("schedule.csv"):
        by.setdefault(r["station_id"], []).append((hm(date, r["inicio"]), hm(date, r["fim"])))
    out = []
    for sid, ws in by.items():
        ws.sort()
        cur = list(ws[0])
        for a, b in ws[1:]:
            if a <= cur[1]:
                cur[1] = max(cur[1], b)
            else:
                out.append((sid, *cur)); cur = [a, b]
        out.append((sid, *cur))
    return sorted(out, key=lambda w: w[1])


def program_at(sid, when):
    for r in rows("schedule.csv"):
        if r["station_id"] == sid and hm(when, r["inicio"]) <= when < hm(when, r["fim"]):
            return r["programa"]
    return ""


def cmd_plan(_):
    st, total, miss = stations(), 0, 0
    for sid, a, b in windows(datetime.now(TZ).date()):
        ok = bool(st[sid]["stream_url"].strip())
        miss += not ok
        total += (b - a).seconds
        print(f"{a:%H:%M}-{b:%H:%M}  {st[sid]['emissora']:<34} {'OK' if ok else 'SEM stream_url'}")
    print(f"\n{total/3600:.1f} h de gravação/dia; {miss} janelas sem stream_url (preencha stations.csv)")


# ---------------------------------------------------------------- captura
def resolve(url):
    if "youtube.com" in url or "youtu.be" in url:  # live do YouTube -> URL do áudio
        return subprocess.check_output(["yt-dlp", "-g", "-f", "bestaudio", url], text=True).split()[0]
    return url


def record(sid, start, end):
    """Grava [start-PAD, end+PAD]; se o stream cair, reabre em novo arquivo."""
    url = stations()[sid]["stream_url"].strip()
    if not url:
        print(f"[{sid}] sem stream_url, pulando"); return []
    d = DATA / "audio" / start.strftime("%Y-%m-%d"); d.mkdir(parents=True, exist_ok=True)
    stop = end + timedelta(seconds=PAD_REC)
    files = []
    while True:
        now = datetime.now(TZ)
        left = (stop - now).total_seconds()
        if left <= 5:
            break
        f = d / f"{sid}_{now:%Y%m%d_%H%M%S}.mp3"
        try:
            src = resolve(url)
        except Exception as e:
            print(f"[{sid}] resolve falhou: {e}"); time.sleep(15); continue
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-reconnect", "1",
                        "-reconnect_streamed", "1", "-reconnect_delay_max", "10", "-i", src,
                        "-t", str(int(left)), "-vn", "-ac", "1", "-ar", "22050",
                        "-c:a", "libmp3lame", "-b:a", f"{KBPS}k", str(f)])
        if f.exists() and f.stat().st_size > 20000:
            files.append(f)
        time.sleep(5)
    return files


def cmd_record(a):
    sid, s, e = a[:3]
    d = datetime.now(TZ).date()
    for f in record(sid, hm(d, s) - timedelta(seconds=PAD_REC), hm(d, e)):
        process(f)


def prune():
    lim = time.time() - KEEP_DAYS * 86400
    for f in (DATA / "audio").rglob("*.mp3"):
        if f.stat().st_mtime < lim:
            f.unlink()


def cmd_daemon(_):
    started, st = set(), stations()
    print("daemon ativo (Ctrl+C para sair)")
    while True:
        now = datetime.now(TZ)
        for sid, a, b in windows(now.date()):
            key = (sid, a)
            if key in started or not (a - timedelta(seconds=PAD_REC) <= now < b):
                continue
            started.add(key)
            print(f"{now:%H:%M} gravando {st[sid]['emissora']} até {b:%H:%M}")
            threading.Thread(target=lambda s=sid, x=a, y=b: [process(f) for f in record(s, x, y)],
                             daemon=True).start()
        prune()
        time.sleep(20)


# ---------------------------------------------------------------- transcrição
def dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", str(f)], text=True))


def asr_openai(f):
    from openai import OpenAI
    cli, segs, words, off = OpenAI(), [], [], 0.0
    with tempfile.TemporaryDirectory() as t:
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(f), "-f", "segment",
                        "-segment_time", str(CHUNK), "-c", "copy", f"{t}/p%04d.mp3"], check=True)
        for p in sorted(Path(t).glob("p*.mp3")):
            with open(p, "rb") as fh:
                r = cli.audio.transcriptions.create(model="whisper-1", file=fh, language="pt",
                                                    response_format="verbose_json",
                                                    timestamp_granularities=["word", "segment"])
            segs += [{"start": s.start + off, "end": s.end + off, "text": s.text.strip()} for s in r.segments]
            words += [{"start": w.start + off, "end": w.end + off, "word": w.word} for w in (r.words or [])]
            off += dur(p)
    return segs, words


def asr_local(f):  # padrão: faster-whisper local, grátis (RADIO_ASR=openai usa a API)
    from faster_whisper import WhisperModel
    m = WhisperModel(os.environ.get("RADIO_MODEL", "small"), compute_type="int8")  # tiny/base/small/medium
    it, _ = m.transcribe(str(f), language="pt", word_timestamps=True, vad_filter=True)
    segs, words = [], []
    for s in it:
        segs.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        words += [{"start": w.start, "end": w.end, "word": w.word} for w in s.words]
    return segs, words


def asr_mlx(f):  # Apple Silicon (M1..M5): usa GPU/Neural do Mac via MLX
    import mlx_whisper
    r = mlx_whisper.transcribe(str(f), language="pt", word_timestamps=True,
                               path_or_hf_repo=os.environ.get("RADIO_MLX_MODEL", "mlx-community/whisper-large-v3-turbo"))
    segs = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()} for s in r["segments"]]
    words = [{"start": w["start"], "end": w["end"], "word": w["word"]} for s in r["segments"] for w in s.get("words", [])]
    return segs, words


def pick_asr():
    e = os.environ.get("RADIO_ASR") or ("mlx" if sys.platform == "darwin" and platform.machine() == "arm64" else "faster")
    return {"openai": asr_openai, "mlx": asr_mlx, "faster": asr_local}[e]


def transcribe(f):
    j = f.with_suffix(".json")
    if j.exists():
        return j
    segs, words = pick_asr()(f)
    sid, ts = f.stem.split("_", 1)
    j.write_text(json.dumps({"audio": f.name, "station_id": sid,
                             "start": datetime.strptime(ts, "%Y%m%d_%H%M%S").replace(tzinfo=TZ).isoformat(),
                             "segments": segs, "words": words}, ensure_ascii=False))
    return j


def cmd_transcribe(a):
    for f in [Path(x) for x in a] or sorted((DATA / "audio").rglob("*.mp3")):
        print("transcrevendo", f.name); transcribe(f)


# ---------------------------------------------------------------- achar + cortar
def clientes():
    return yaml.safe_load(open(HERE / "clientes.yaml", encoding="utf-8"))["clientes"]


def find_hits(segs):
    """[(cliente, termo, idx_seg_inicial, idx_seg_final)] — acha termos mesmo quebrados entre segmentos."""
    text, spans = "", []
    for s in segs:
        spans.append((len(text), len(text) + len(s["text"]))); text += s["text"] + " "
    ft, out = fold(text), []
    for c in clientes():
        for t in c["termos"]:
            for m in re.finditer(r"(?<!\w)" + re.escape(fold(t)) + r"(?!\w)", ft):
                i = next(k for k, (a, b) in enumerate(spans) if a <= m.start() < b + 1)
                j = next(k for k, (a, b) in enumerate(spans) if a <= m.end() - 1 < b + 1)
                out.append((c["nome"], t, i, j))
    return out


def bounds_gap(segs, i, j):
    """Sem IA: expande até silêncio > GAP ou MAX_SIDE."""
    a, b = i, j
    while a > 0 and segs[a]["start"] - segs[a - 1]["end"] < GAP and segs[i]["start"] - segs[a - 1]["start"] < MAX_SIDE:
        a -= 1
    while b < len(segs) - 1 and segs[b + 1]["start"] - segs[b]["end"] < GAP and segs[b + 1]["end"] - segs[j]["end"] < MAX_SIDE:
        b += 1
    return a, b


def llm_json(system, user):
    """RADIO_LLM=ollama (grátis/local, modelo em RADIO_LLM_MODEL) ou OpenAI gpt-4o-mini."""
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if os.environ.get("RADIO_LLM") == "ollama":
        import requests
        r = requests.post("http://localhost:11434/api/chat", timeout=300, json={
            "model": os.environ.get("RADIO_LLM_MODEL", "qwen2.5:7b"), "messages": msgs,
            "format": "json", "stream": False, "options": {"temperature": 0}})
        return r.json()["message"]["content"]
    from openai import OpenAI
    r = OpenAI().chat.completions.create(model="gpt-4o-mini", temperature=0,
                                         response_format={"type": "json_object"}, messages=msgs)
    return r.choices[0].message.content


def bounds_llm(segs, i, j, termo):
    """IA (gpt-4o-mini) decide onde a matéria começa e termina dentro da janela."""
    lo = max(0, i - 40); hi = min(len(segs) - 1, j + 40)
    while lo < i and segs[i]["start"] - segs[lo]["start"] > MAX_SIDE: lo += 1
    while hi > j and segs[hi]["end"] - segs[j]["end"] > MAX_SIDE: hi -= 1
    lines = "\n".join(f"[{k}] ({segs[k]['start']:.1f}s) {segs[k]['text']}" for k in range(lo, hi + 1))
    system = ("Você recorta matérias de radiojornal. Recebe trechos numerados de uma transcrição. "
              "Devolva JSON {\"inicio\":n,\"fim\":n}: primeiro e último trecho da MATÉRIA (um único assunto/"
              "reportagem/nota) que contém a menção. O início é a chamada/abertura do assunto (inclua a "
              "frase do apresentador que introduz); o fim é a última frase antes de mudar de assunto, "
              "vinheta, comercial ou chamada de outro tema. Não inclua matérias vizinhas.")
    user = f"Menção: {termo!r} nos trechos {i}-{j}.\n\n{lines}"
    d = json.loads(llm_json(system, user))
    a, b = int(d["inicio"]), int(d["fim"])
    return (a, b) if lo <= a <= i and j <= b <= hi else bounds_gap(segs, i, j)


def cut_file(jpath):
    T = json.loads(Path(jpath).read_text())
    segs, base = T["segments"], datetime.fromisoformat(T["start"])
    audio = Path(jpath).with_name(T["audio"])
    st = stations()[T["station_id"]]
    use_llm = (os.environ.get("RADIO_LLM") == "ollama" or bool(os.environ.get("OPENAI_API_KEY"))) and os.environ.get("RADIO_BOUNDS") != "gap"
    # 1 clipe por (cliente, matéria): funde menções que caem na mesma matéria
    clips = {}
    for cli, termo, i, j in find_hits(segs):
        a, b = bounds_llm(segs, i, j, termo) if use_llm else bounds_gap(segs, i, j)
        for (c2, a2, b2), v in list(clips.items()):
            if c2 == cli and a <= b2 and a2 <= b:   # sobrepõe
                del clips[(c2, a2, b2)]; a, b = min(a, a2), max(b, b2); v["termos"].add(termo); break
        else:
            v = {"termos": {termo}}
        clips[(cli, a, b)] = v
    out = []
    for (cli, a, b), v in clips.items():
        t0, t1 = max(0, segs[a]["start"] - PAD_CLIP[0]), segs[b]["end"] + PAD_CLIP[1]
        when = base + timedelta(seconds=t0)
        d = DATA / "clips" / re.sub(r"\W+", "_", fold(cli)); d.mkdir(parents=True, exist_ok=True)
        f = d / f"{when:%Y%m%d_%H%M%S}_{T['station_id']}.mp3"
        if not f.exists():
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", str(audio), "-ss", f"{t0:.2f}",
                            "-to", f"{t1:.2f}", "-c:a", "libmp3lame", "-b:a", "96k", str(f)], check=True)
        out.append({"data_hora": f"{when:%Y-%m-%d %H:%M:%S}", "cliente": cli, "termos": "; ".join(sorted(v["termos"])),
                    "emissora": st["emissora"], "programa": program_at(T["station_id"], when),
                    "duracao_s": round(t1 - t0, 1), "arquivo": str(f),
                    "texto": " ".join(s["text"] for s in segs[a:b + 1])})
    if out:
        log = DATA / "clips.csv"; new = not log.exists()
        with open(log, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0])); new and w.writeheader(); w.writerows(out)
    return out


def cmd_cut(a):
    for j in [Path(x) for x in a] or sorted((DATA / "audio").rglob("*.json")):
        for c in cut_file(j):
            print(f"{c['cliente']}: {c['arquivo']} ({c['duracao_s']}s) — {c['programa']}")


def process(f):
    try:
        for c in cut_file(transcribe(f)):
            print("CLIPE", c["cliente"], c["arquivo"])
    except Exception as e:
        print("erro em", f.name, e)


if __name__ == "__main__":
    cmds = {"plan": cmd_plan, "daemon": cmd_daemon, "record": cmd_record, "transcribe": cmd_transcribe, "cut": cmd_cut}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[sys.argv[1]](sys.argv[2:])
