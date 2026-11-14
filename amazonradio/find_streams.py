#!/usr/bin/env python3
"""Procura URLs diretas de áudio (mp3/aac/m3u8/icecast) nas páginas de cada emissora
e preenche stream_url em stations.csv quando acha exatamente uma candidata.
Confira o resultado: ffplay URL.   Uso: python find_streams.py [--write]"""
import csv, re, sys
from pathlib import Path
import requests

P = Path(__file__).parent / "stations.csv"
PAT = re.compile(r"https?://[^\s\"'<>\\]+?(?:\.m3u8|\.aac|\.mp3|/stream|;stream\.mp3|/listen)[^\s\"'<>\\]*", re.I)
rows = list(csv.DictReader(open(P, encoding="utf-8")))
for r in rows:
    if r["stream_url"]:
        continue
    url = r["portal_url"]
    if "youtube.com" in url:
        r["stream_url"] = url; print(f"{r['station_id']}: YouTube (usa yt-dlp)"); continue
    try:
        html = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}).text.replace("\\/", "/")
    except Exception as e:
        print(f"{r['station_id']}: ERRO {type(e).__name__}"); continue
    c = sorted({m.rstrip("\\,);") for m in PAT.findall(html) if not m.endswith((".jpg", ".png"))})
    print(f"{r['station_id']}: {len(c)} candidata(s) {c[:3]}")
    if len(c) == 1:
        r["stream_url"] = c[0]
if "--write" in sys.argv:
    with open(P, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
