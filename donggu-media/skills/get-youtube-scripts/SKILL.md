---
name: get-youtube-scripts
description: Use when given a YouTube URL (watch, youtu.be, shorts, live) and you need the video's transcript / captions / 자막 / 스크립트 as clean text to summarize (요약), translate, quote, or analyze — returned to the conversation, nothing saved. To save the video as a note in the Obsidian vault, use make-source instead. Captions-only, no audio transcription.
---

# get-youtube-scripts

Pull a YouTube video's captions as clean plain text + metadata using **yt-dlp**. Output is the transcript only — summarizing / translating / quoting is the caller's job.

**Why yt-dlp (not youtube-transcript-api):** yt-dlp tracks YouTube's changes far more aggressively, and youtube-transcript-api gets PoToken-blocked from cloud IPs (2025–2026). yt-dlp works from a residential IP.

## When to use
- A YouTube link is dropped and the 자막 / 스크립트 / transcript is wanted, or a video should be 요약/summarized/analyzed.
- Any URL form — `watch?v=`, `youtu.be/`, `/shorts/`, `/live/`. **Pass the URL straight to yt-dlp; never parse the video id by hand.**

**When NOT to use:** the video has no captions at all → report `자막 없음` and stop. Audio→text (Whisper) is out of scope.

## The one trap that matters: pick the source (`-orig`) track

YouTube exposes EVERY language as an auto-translation. The source track is suffixed **`-orig`** (`ko-orig`, `en-orig`, …). The bare 2-letter code (`ko`, `en`) can be a lossy auto-translation of the original *back into its own language*. So the procedure **discovers the real track list first and selects ONE track by explicit priority** — it never trusts file-glob order, and it never bulk-downloads every language (that triggers `429`).

Priority order: `<lang>-orig` → bare `<lang>`, **manual preferred over auto-generated**. Edit `PRIORITY` for a non-ko/en video.

## Procedure (run as one block)

```bash
URL="https://www.youtube.com/watch?v=VIDEO_ID"   # any youtube url form works
WORK="$(mktemp -d)"

# 0. ensure yt-dlp (single binary; tracks YouTube changes)
command -v yt-dlp >/dev/null || pip3 install -q yt-dlp   # or: brew install yt-dlp

# 1. ONE discovery call: metadata + the real caption-track lists (manual vs auto)
yt-dlp -J --no-playlist --skip-download "$URL" > "$WORK/info.json"

# 2. select exactly one track by priority (manual > auto). Writes "$WORK/sel" = "<lang> <kind>"
python3 - "$WORK" <<'PY'
import sys, json, os
work = sys.argv[1]
info = json.load(open(os.path.join(work, "info.json"), encoding="utf-8"))
print("title   :", info.get("title"))
print("channel :", info.get("channel"))
print("duration:", info.get("duration_string"))
print("video_id:", info.get("id"))
manual = info.get("subtitles") or {}
auto   = info.get("automatic_captions") or {}
PRIORITY = ["ko-orig", "en-orig", "ko", "en"]   # prepend other source langs, e.g. "ja-orig","ja"
def pick(d):
    for c in PRIORITY:
        if c in d:
            return c
    origs = sorted(k for k in d if k.endswith("-orig"))   # else any source track, deterministic
    return origs[0] if origs else (sorted(d)[0] if d else None)
track, kind = pick(manual), "manual"
if not track:
    track, kind = pick(auto), "auto"
open(os.path.join(work, "sel"), "w").write(f"{track or ''} {kind if track else 'none'}")
print("track   :", track, f"({kind})" if track else "(none → 자막 없음)")
PY
read TRACK KIND < "$WORK/sel"
[ -z "$TRACK" ] && { echo "자막 없음"; exit 0; }

# 3. download ONLY that one track as json3 (json3 = no VTT timestamps / no rolling-caption dupes)
[ "$KIND" = auto ] && SUBFLAG=--write-auto-subs || SUBFLAG=--write-subs
yt-dlp --skip-download --no-playlist $SUBFLAG --sub-langs "$TRACK" --sub-format json3 \
  -o "$WORK/cap" "$URL"

# 4. json3 -> clean text
python3 - "$WORK/cap.$TRACK.json3" <<'PY'
import sys, json, re
data = json.load(open(sys.argv[1], encoding="utf-8"))
text = "".join(seg.get("utf8", "")
                for ev in data.get("events", [])
                for seg in (ev.get("segs") or []))
text = re.sub(r"\s*\n\s*", " ", text)
text = re.sub(r"\s{2,}", " ", text).strip()
text = text.replace(">>", " ").strip()   # auto-caption speaker-turn markers
print(text)
PY
```

`TRACK` (e.g. `ko-orig`) and `KIND` (`manual`/`auto`) give you the output contract's `lang` and `auto` directly. No second `--list-subs` call needed.

## Output contract (return to caller)
`title` · `channel` · `duration` · `video_id` · `lang` (= `TRACK`) · `auto` (= `KIND == auto`) · `transcript` (clean text)

## Common mistakes
| Mistake | Fix |
|---|---|
| Trusting glob / `files[0]` to pick the track | Select by explicit `PRIORITY` from `-J` lists — glob order is filesystem-dependent and can pick the lossy `ko` over `ko-orig` |
| `--sub-langs "ko-orig,en-orig,ko,en"` to "get the best one" | That downloads **every** matching language (→ `429 Too Many Requests`). Discover first, then download ONE `--sub-langs "$LANG"` |
| Used bare `ko`/`en`, phrasing reads "off" | Source track is `-orig`; priority puts it first |
| Parsed VTT → timestamps + duplicated rolling lines | Use `--sub-format json3`, parse `segs[].utf8` |
| Treated a WARNING (no JS runtime / ffmpeg / impersonation) or a `429`/`ERROR` on a **non-selected** track as failure | Harmless. Real failure = the selected `cap.$LANG.json3` is missing. Persistent hard failure → install a JS runtime (`deno`) |
| Reached for youtube-transcript-api, got blocked | PoToken blocks cloud IPs; yt-dlp is the robust path |
| `rm cap.*` → zsh `no matches found` | Work inside the `mktemp -d` dir; don't glob-delete |
| Genuinely no captions | Report `자막 없음`; do not transcribe audio (out of scope) |

## Real-world check
잡소리 ep.43 (27:32) → selected `ko-orig` (manual) over the lossy `ko` track → ~15,000 chars clean text, single track, no 429. Verified 2026-06-12.
