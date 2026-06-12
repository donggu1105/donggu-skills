#!/usr/bin/env python3
"""Assemble a CapCut draft for a 9:16 short — scenes + narration + subtitles.

Creates a real CapCut desktop draft (1080×1920, 30fps) the user opens, tweaks,
exports, and uploads manually. Built on pyCapCut (draft_content.json generator).

Usage:
  python3 capcut_draft.py <name> <narration.mp3> <narration.srt> \
      <scene1.png,scene2.png,...> [durations_sec_csv] [draft_folder]

  - scenes: comma-separated image paths, in order.
  - durations: optional comma CSV (sec per scene). Default = audio duration
    split evenly across scenes (last scene absorbs the remainder).
  - draft_folder default: ~/Movies/CapCut/User Data/Projects/com.lveditor.draft

Stdout JSON: {"draft": <name>, "path": ..., "scenes": N, "total_sec": float}
Requires: pip install pyCapCut  (+ CapCut desktop to open the result)
"""
import json
import os
import subprocess
import sys

import pycapcut as cc
from pycapcut import trange, TrackType

name, mp3, srt = sys.argv[1], sys.argv[2], sys.argv[3]
images = [p for p in sys.argv[4].split(",") if p]
dur_csv = sys.argv[5] if len(sys.argv) > 5 else ""
folder = sys.argv[6] if len(sys.argv) > 6 else os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft")

if not images:
    sys.exit("no scene images")
for p in [mp3, srt] + images:
    if not os.path.exists(p):
        sys.exit(f"missing file: {p}")


def audio_duration(path: str) -> float:
    """macOS 내장 afinfo로 mp3 길이(초). ffprobe 불필요."""
    out = subprocess.run(["afinfo", path], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "estimated duration" in line:
            return float(line.split(":")[1].strip().split()[0])
    sys.exit("could not read audio duration (afinfo)")


total = audio_duration(mp3)
if dur_csv:
    durs = [float(x) for x in dur_csv.split(",")]
    if len(durs) != len(images):
        sys.exit("durations count != scenes count")
else:
    base = total / len(images)
    durs = [round(base, 2)] * len(images)
    durs[-1] = round(total - base * (len(images) - 1), 2)  # 마지막이 잔여 흡수

df = cc.DraftFolder(folder)
script = df.create_draft(name, 1080, 1920, fps=30, allow_replace=True)
script.add_track(TrackType.video, "scenes")
script.add_track(TrackType.audio, "narration")

t = 0.0
for img, d in zip(images, durs):
    seg = cc.VideoSegment(img, trange(f"{t}s", f"{d}s"))
    script.add_segment(seg, "scenes")
    t += d

script.add_segment(cc.AudioSegment(mp3, trange("0s", f"{total}s")), "narration")
script.import_srt(srt, "subtitles")
script.save()

print(json.dumps({"draft": name, "path": os.path.join(folder, name),
                  "scenes": len(images), "total_sec": round(total, 2)},
                 ensure_ascii=False))
