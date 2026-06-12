---
name: make-shorts
description: Use when turning a news item, article, or topic into a short-form vertical video (쇼츠, 숏폼, Shorts, Reels, 릴스) — produces a ready-to-edit CapCut draft with narration, scene cards, and subtitles. Especially for AI/AX/dev news with the user's own commentary voice. Source gathering is a separate skill; this skill starts from a given source text.
---

# make-shorts

Turn one news/topic + the user's take into a **9:16 CapCut draft** (scene cards + narration + subtitles) the user opens, tweaks, exports, and uploads. Source gathering is NOT here — this skill receives source text and produces the draft.

**Core split**: agent owns judgment (news angle, script, scene plan); helpers own mechanics (render, TTS, draft assembly). The user owns the final cut (HITL: preview → approve → they export from CapCut).

## Pipeline

```
source text (given) →
  1. SCRIPT (agent, judgment)   30–45s, the user's voice
  2. SCENE PLAN (agent)         one idea per scene, 4–6 scenes
  3. RENDER scenes (helper)     9:16 cards via render webhook
  4. NARRATION (helper)         tts.py → mp3 + srt + duration
  5. PREVIEW + APPROVAL (HITL)  show script + scene images, get explicit "ㄱ"
  6. ASSEMBLE (helper)          capcut_draft.py → CapCut draft folder
  7. REPORT                     "CapCut 열면 <name> 있어요" + manual export/upload
```

### 1. Script (the user's voice — the differentiator)
Not a neutral news read. Structure = the user's 링크드인 해체 패턴, applied to news:
**훅(공감/자기경험 1줄) → 무슨 일(뉴스 핵심) → "근데 개발자/AX 관점엔 이게 포인트"(본인 해석) → 질문 맺음.**
해요체+습니다체 혼용, 문장 짧게(쇼츠는 귀로 들음), 1문장=1호흡. 30–45초 = 한국어 ~90–130자.
관점이 콘텐츠의 핵심 — 단순 전달이면 경쟁자와 안 갈림. 브랜드 = 프로덕트엔지니어·AI·AX.

### 2. Scene plan
Cover(훅) → 본문 카드 N개(한 장면=한 메시지) → 마무리(질문/태그). 자막은 narration이 깔리니
카드 텍스트는 **짧은 키워드/숫자**만(문장 통째로 넣지 말 것 — 자막과 중복). 디자인은
make-insta-card-news의 카드 문법 재사용하되 **9:16(1080×1920) 풀스크린**.

### 3. Render scenes (helper = render webhook, channel `shorts`)
Self-contained HTML(절대 URL only — `make-insta-card-news` Mode B 규칙 동일) →
`POST https://n8n.donggu.site/webhook/sns-render-shorts` (`X-SNS-Token`) body `{html, slug}`
→ `{image_urls,...}` (1080×1920, 2160×3840 출력). 장면 순서 = image_urls 순서.

### 4. Narration (helper)
```bash
python3 tts.py <script.txt> <out_dir> [voice] [rate]
# → {"mp3","srt","duration_sec"}.  default voice ko-KR-HyunsuNeural, rate +8%
```
기본 = edge-tts(무료·무키). **사용자 ElevenLabs 보이스 클론이 준비되면 tts.py의 엔진만 교체** —
스킬 계약(mp3+srt+duration)은 불변. `script.txt`는 1번 나레이션 텍스트 그대로(자막=문장 단위).

### 5. Preview + approval (HITL — 절대 생략 금지)
디스코드/대화에 **대본 전문 + 장면 이미지**를 보여주고 명시 승인("ㄱ"/"올려"/"좋아")을 받는다.
공개 게시물의 씨앗이므로 — 승인 전 드래프트 조립까지는 해도 되나, **사용자가 보기 전에 "끝났다"고 하지 않는다.**

### 6. Assemble CapCut draft (helper)
```bash
python3 capcut_draft.py <name> <mp3> <srt> <scene1.png,scene2.png,...> [durations_csv]
# → ~/Movies/CapCut/User Data/Projects/.../<name>  (1080×1920, 30fps)
# 트랙: video(scenes) + audio(narration) + text(srt 자막). durations 생략 시 오디오 길이 균등분할.
```
이미지는 **로컬 파일 경로**를 넘긴다(렌더 결과를 `curl`로 받아 /tmp에 저장 후 경로 전달).
원격 URL 아님 — CapCut 드래프트는 로컬 미디어 참조.

### 7. Report
"CapCut 열면 `<name>` 프로젝트 있어요. 씬 N개·약 Xs·9:16·자막 포함. 전환/폰트는 CapCut에서
다듬고 내보내서 올리시면 돼요." 발행 자동화(YouTube/Reels 업로드)는 이 스킬 범위 밖 — 나중 증분.

## Quick reference

| 단계 | 도구 | 핵심 |
|------|------|------|
| 대본 | 에이전트 | 훅→뉴스→관점→질문, ~90–130자, 본인 보이스 |
| 장면 렌더 | `sns-render-shorts` 웹훅 | 9:16, 자급자족 HTML(절대 URL), 카드텍스트=키워드만 |
| 나레이션 | `tts.py` | edge-tts 기본, mp3+srt+duration. 엔진 교체점 1곳 |
| 조립 | `capcut_draft.py` | pyCapCut, 로컬 이미지 경로, srt 자막 트랙 |
| 마무리 | 사용자 | CapCut에서 export+업로드 (HITL) |

## Common mistakes

- **장면 카드에 대본 문장을 통째로 박음** → 자막과 중복. 카드는 키워드/숫자, 문장은 자막(srt)이 깐다.
- **원격 URL을 capcut_draft.py에 넘김** → 드래프트는 로컬 미디어 참조. 렌더 PNG를 `/tmp`에 받아 경로 전달.
- **관점 없는 뉴스 전달** → 차별화 0(유튜브가 죽이는 양산형). 반드시 "개발자/AX 관점 한 방".
- **미리보기 없이 "완성"** → 공개 콘텐츠. 대본+장면 보여주고 승인받는다(HITL).
- **9:16인데 4:5 카드 문법 그대로** → 세로가 길다. 텍스트 수직 중앙·여백 넉넉히.

## Files
- `tts.py` — 나레이션 TTS(edge-tts→mp3+srt+duration). ElevenLabs 클론 전환 시 여기 엔진만 교체.
- `capcut_draft.py` — pyCapCut으로 9:16 드래프트 조립(scenes+narration+자막). CapCut 데스크톱이 열 결과물.

설치: `pip install edge-tts pyCapCut`. 발행(업로드)은 별도 — 본 스킬은 **편집 직전 드래프트까지**.
