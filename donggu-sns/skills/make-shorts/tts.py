#!/usr/bin/env python3
"""Narration TTS for shorts — text → mp3 + srt + duration (JSON to stdout).

Default engine: edge-tts (free, no key, Korean neural voices). When the user's
ElevenLabs voice clone is ready, swap the engine HERE (one place) — the skill
contract (mp3 + srt + duration) stays the same.

Usage:
  python3 tts.py <script.txt> <out_dir> [voice] [rate]
  # voice default ko-KR-HyunsuNeural (male, calm). Alt: ko-KR-InJoonNeural,
  # ko-KR-SunHiNeural (female). rate default "+8%" (shorts pace).

Output files: <out_dir>/narration.mp3, <out_dir>/narration.srt
Stdout JSON: {"mp3": ..., "srt": ..., "duration_sec": float}
Requires: pip install edge-tts
"""
import asyncio
import json
import os
import sys

import edge_tts

text_path, out_dir = sys.argv[1], sys.argv[2]
voice = sys.argv[3] if len(sys.argv) > 3 else "ko-KR-HyunsuNeural"
rate = sys.argv[4] if len(sys.argv) > 4 else "+8%"

text = open(text_path, encoding="utf-8").read().strip()
if not text:
    sys.exit("script text empty")
os.makedirs(out_dir, exist_ok=True)
mp3 = os.path.join(out_dir, "narration.mp3")
srt = os.path.join(out_dir, "narration.srt")


async def run() -> float:
    # SentenceBoundary = 문장 단위 자막(쇼츠 캡션에 적합). edge-tts 7.x 기본.
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="SentenceBoundary")
    sub = edge_tts.SubMaker()
    end_ticks = 0  # 100ns ticks
    with open(mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"].endswith("Boundary"):
                sub.feed(chunk)
                end_ticks = max(end_ticks, chunk["offset"] + chunk["duration"])
    with open(srt, "w", encoding="utf-8") as f:
        f.write(sub.get_srt())
    return end_ticks / 10_000_000  # → seconds


dur = asyncio.run(run())
print(json.dumps({"mp3": mp3, "srt": srt, "duration_sec": round(dur, 2)},
                 ensure_ascii=False))
