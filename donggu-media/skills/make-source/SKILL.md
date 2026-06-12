---
name: make-source
description: Use when the user wants to capture / save / 노트화 / 아카이브 a YouTube video as a reference source note in their Obsidian vault (남의 영상 스와이프·레퍼런스) — i.e. they want it SAVED, not just read. Trigger phrases like 옵시디언에 저장·소스로 남겨·노트로 박아·스와이프 자료로 남겨둬. If they only want the transcript or a chat summary (nothing saved), use get-youtube-scripts instead. Not for writing the user's own video scripts.
---

# make-source

Turn a YouTube video into a **reference SOURCE note** in the Obsidian vault: summary on top + jump-to timestamps (clickable deep-links) + key quotes. This captures **other people's** videos as swipe/reference material to mine for content.

**Composes get-youtube-scripts** for the transcript (yt-dlp). This skill adds timestamps, a summary, and the vault note. The agent (you) writes the summary — that's the point of the skill.

## Save location (fixed)

```
Personal Branding/00_Inbox/SOURCE - <라벨>.md
```

- **`Personal Branding/00_Inbox/`** is the single capture inbox (the `00` slot of the 00~80 numbering scheme) — every capture lands here first, then gets filed later. **NOT vault-root `Inbox/`** (doesn't exist — don't create it), **NOT `10_Sources/`** (curated 1:1-indexed box, things get *promoted* there later), and **NOT** buried deep in a channel pack.
- **Filename**: `SOURCE - <짧은 한글 라벨>.md`, **no date suffix**. Token order: `<시리즈 epNN> <채널/출처> <게스트> <토픽>` → e.g. `SOURCE - 잡소리 ep43 원티드 정기수 AX`.

## Procedure

### 1. Fetch transcript WITH timestamps
Run **get-youtube-scripts** steps 0–3 to get `$WORK/cap.$TRACK.json3` and the metadata.

**No-caption guard — STOP here if there are no captions.** If get-youtube-scripts reports `자막 없음` (no manual *and* no auto caption track), **do NOT create a note.** Tell the user plainly, e.g. *"이 영상은 자막이 없어 소스 노트로 만들 수 없어요 (자막 없는 영상은 미지원)."* — optionally suggest checking whether another upload of the same video has captions. Caption-less videos are **out of scope by design** (no audio→text / Whisper). Don't fabricate a note from nothing.

Otherwise, parse **keeping timestamps** (get-youtube-scripts' default parser strips them):

```bash
python3 - "$WORK/cap.$TRACK.json3" <<'PY'
import sys, json, re
data = json.load(open(sys.argv[1], encoding="utf-8"))
prev = None
for ev in data.get("events", []):
    txt = "".join(s.get("utf8", "") for s in (ev.get("segs") or []))
    txt = re.sub(r"\s+", " ", txt).replace(">>", " ").strip()
    if not txt or txt == prev:          # drop blanks + rolling-caption dupes
        continue
    prev = txt
    s = ev.get("tStartMs", 0) // 1000
    print(f"{s//60:02d}:{s%60:02d}\t{s}\t{txt}")   # mm:ss <tab> seconds <tab> text
PY
```
The middle column (seconds) is what the deep-links need. Pull `title / channel / duration / id / upload_date` from `info.json`.

### 2. Summarize + pick key moments (you)
- Write a **한 줄 요약** (one blockquote) + a **요약 (다이제스트)** bullet list.
- Pick **topic-pivot moments** for a jump-table (~one per section, ~12–25 total) and a tighter **★ 핵심 인용** list.
- **Deep-link format**: `[15:42](https://youtu.be/<id>?t=942)` — `t` = the seconds column.
- ⚠️ **Auto-captions are lossy** (오타·띄어쓰기·동음오류 — e.g. "구트위터"→"구 트위터", "성가"→"성과"). Lightly normalize quotes and **flag that exact wording needs a spot-check before publishing as someone's words.** Timestamps are reliable; wording is not.

### 3. Write the note
Path above. Do **not** embed the full transcript (the summary + jump-links are the deliverable; re-fetch via get-youtube-scripts if the raw text is ever needed).

```markdown
---
type: source
source_type: video
url: <url>
channel: <channel>
topics: [..]
created: <today YYYY-MM-DD>
---

# SOURCE - <라벨>

## 메타데이터
- **출처**: <채널> / <시리즈·맥락>
- **URL**: <url>
- **영상 제목**: <full youtube title>
- **게시일**: <upload_date> · **길이**: <duration>
- **출연/형식**: <interviewee> · <format>

## 한 줄 요약
> **<핵심 한 문장>**

## 요약
- <다이제스트 bullets>

## ⏱️ 타임스탬프 (점프)
| 시간 | 구간 |
|---|---|
| [01:32](https://youtu.be/<id>?t=92) | <topic> |
…
### ★ 핵심 인용
- **[13:50](…?t=830)** "<quote>" — <why it matters>

## 💡 나의 연결점 / 적용
- <how to reuse: LinkedIn / Blog / 세미나 angles>

## 🔗 연결된 Core / MOC
- <only link [[CORE - …]] / [[MOC - …]] AFTER verifying the exact filename exists>

## 태그
#source #video #<topics>
```

**Before adding `[[CORE - …]]`/`[[MOC - …]]`**, list `Personal Branding/20_Core/` and `Personal Branding/60_MOCs/Topics/` and link only real filenames (baseline guessed MOC titles that didn't exist). `MOC - AX Bridge` is usually the home for AX/AI videos.

## Common mistakes (from baseline)
| Mistake | Fix |
|---|---|
| Saved to vault-root `Inbox/`, `10_Sources/`, or buried in a channel pack | All captures → `Personal Branding/00_Inbox/` (file later) |
| Used get-youtube-scripts' default parser | It flattens away timestamps; use the timestamp-keeping parse above |
| Plain `[mm:ss]` text | Make them clickable `[mm:ss](https://youtu.be/ID?t=<sec>)` |
| Quoted auto-captions verbatim as fact | Flag 자동생성 → spot-check before publishing |
| Guessed `[[CORE - …]]`/`[[MOC - …]]` titles to look thorough | Only link what you've verified exists; otherwise leave the section thin |
| Embedded the 15k-char raw transcript | Don't — summary + jump-links are the artifact; re-fetch if needed |
| Invented frontmatter fields per note | Use the fixed schema above (no volatile fields like view count) |
| Made a note for a caption-less video (empty/ASR) | No captions → STOP, tell the user; caption-less videos are out of scope |

## Real-world check
잡소리 ep.43 (원티드 정기수 AX, 27:32) → `Personal Branding/00_Inbox/SOURCE - 잡소리 ep43 원티드 정기수 AX.md`, summary + ~25 jump-links. Verified 2026-06-12. (애초 vault-root `Inbox/`에 저장했다가 2026-06-12 `00_Inbox`로 교정)
