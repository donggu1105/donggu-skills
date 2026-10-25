---
name: make-card-news
description: Use when the user wants 카드뉴스 / a carousel (LinkedIn document post, Instagram carousel, Threads image set) built from a brief or finished copy. Renders a JSON card spec to 1080×1350 PNGs + one PDF with headless Chrome, runs layout QA, keeps the editable source. Also answers "카드뉴스 만들어주는 서비스 있어?" from references/tool-landscape.md. Does not write the copy (writing-social-content) and does not publish (publish-sns).
---

# make-card-news

Turn approved copy into a multi-card set (카드뉴스, carousel): per-card PNGs for Instagram/Threads, one merged PDF for a LinkedIn document post, and a JSON source you can edit one card at a time. Text stays text (HTML/CSS → Chrome screenshot), so a typo on card 4 is a one-line fix and a re-render, not a regenerated image.

## When to use

- "이 글 카드뉴스로 만들어줘", round promos, recap or insight series, "링크드인 캐러셀로".
- Picking a path: in-house renderer (this skill) vs a SaaS generator → `references/tool-landscape.md`.
- Not for: writing the copy (`writing-social-content`), a single infographic image (`baoyu-infographic`), or posting (`publish-sns`).

## Iron rules

1. **Copy is locked before layout.** Claims, numbers, names and sources come from the approved text verbatim. The spec may shorten for the card format, never add facts.
2. **Text is never baked into generated images.** Photos and illustrations come from the user's own assets (event photos already published on their site, approved brand illustrations) or `get-ai-image`; all words are rendered by the template so they stay editable and legible.
3. **Every set carries images, and body type is headline-sized.** A text-only white set was rejected as "너무 별로". Body copy stays at the template sizes (≥48 px); if it doesn't fit, cut words, never shrink type.
4. **Default look is `layout: "cinematic"` — the cover treatment on every card.** Full-bleed photo, dark gradient, white type, accent only on the kicker / one highlighted phrase / the stat number / list markers. No chrome: no top bar, no footer rule, no series pill, no page counter; the handle appears small on the first and last card only. The user picked this over every white/wash variant ("맛이 없다", "상단 하단 줄있는거부터가 별로" → "난 F", 2026-10-25). The old white + wash + band look is still `layout: "classic"` — use it only when asked. A separate "dark theme" (dark UI colours) was declined; cinematic is photo-dark, not a theme.
5. **Faces are a liability, not decoration.** Every head in a cinematic card must either sit clearly above the copy (≥ 70 px air under the chin) or be fully buried in the dark scrim under it — never straddling the first line, never sliced by a frame edge. Adjacent cards never share a photo or the same person (one speaker twice in a row reads as a duplicate). Measure, don't eyeball: see "Crops" in the procedure.
6. **Identifiable people get a clearance decision, not a question to the user.** When a set carries a recognisable participant, run `content-rights-clearance` yourself: name the proposed use, read the governing record (for Beyond Deploy: the privacy policy's "현장 사진·영상·녹음" row and `Operations/POLICY - 녹음과 공유` in the vault), state the gap, and write the decision per person into the channel note's `## 사진과 동의`. If the policy's mechanism is notice + opt-out (BD since round 4), draft the notice as a `KakaoTalk - …` channel note and hand it to the host to post — don't ask the host "did you tell them?" and don't invent individual consent that was never recorded. Opt-out = swap that card's photo for a back-of-head/empty-room frame and re-render; never argue.
7. **Count before you report.** Say "N장" only after listing the output directory — PNG files, not spec or HTML files. `qa.json` is the evidence.
8. **Production ≠ publishing.** Deliver files and the source path, state draft/final, stop. Publishing goes through `publish-sns` after the user's explicit approval.
9. **No fake buttons.** Nothing inside a card image is tappable — Instagram carousels have no in-image links, and LinkedIn disables links inside document PDFs. The closing `cta` is a sentence with an arrow, never a pill/button, never a URL, never "클릭/눌러/탭". Point to a native action instead (저장, 공유, 댓글, 프로필 링크, 첫 댓글) and hand the URL to the caption via `writing-social-content`. The validator rejects URLs and click verbs in `cta`.
10. **Korean first.** The template uses `word-break: keep-all`; the QA probe confirms the primary font actually loaded. Fix orphans with a non-breaking space in the spec (`100여\u00a0명`) or a manual `\n`, not by shrinking fonts below the template sizes.

## Procedure

1. **Frame** — content type (회차 홍보 / 후기·필드노트 요약 / 인사이트 / 개인 글), target platform(s), theme (`beyond-deploy` for Beyond Deploy content, `donggu` for the user's personal channels, or a new `themes/<name>.json`), and the approved source text.
2. **Outline per card** — 7–9 cards: cover → hook (quote or point) → **stat** (one number + one line, the second hook) → 2–4 content cards (point / list / compare / steps, one claim each) → closing with one CTA. The first three cards must each stop a reader who has no context — Instagram re-serves card 2 and 3 as fresh posts, and LinkedIn's 2026 feed test shows cards 1–2 side by side. Never make every card the same bullet list. Card types and field limits: `references/card-spec.md`.
3. **Pick images** — download/copy them next to the spec (`assets/`), JPEG/PNG/WebP, under ~400 KB each. Remote URLs are refused on purpose — fetch first so the set is reproducible. In `cinematic` every card is `full`: give each card its own `image` (`focus`, optional `zoom` 1–1.3, `overlay` ≈ 0.8); cards without one fall back to the set `backdrop`. Plan the rotation first — 3–4 photos for 8 cards, never the same photo or the same person on two adjacent cards.
   **Crops (do this, it saves 5+ review rounds):** render once, read each card's copy top from `qa.json` (`min(elements[].top)`; subtract ~60 px for a kicker), get head boxes for every person in every photo (Apple Vision `VNDetectFaceRectanglesRequest` via a tiny Swift script on macOS, plus a vision pass over a 10 % grid for backs of heads/blurred heads that face detection misses), then compute where each head lands for a given `focus`/`zoom` (object-fit cover scale = max(1080/w, 1350/h); zoom scales around the focus point) and keep only crops where every head is ≥ 70 px above the copy top or ≥ 40 px below it, inside the frame with ≥ 24 px headroom. A `focus` y of `100%` with zoom pushes heads up and away from the copy; `0%` pulls the top of the frame in.
4. **Write the spec** — JSON as in `examples/sample-bd.json` (`"layout": "cinematic"`). `handle` is the small first/last-card signature (`series` is shown only in `classic`). `**bold**` inside text becomes an accent highlight; `\n` is a line break; nothing else is markup.
5. **Render** — `python3 scripts/render_cards.py SPEC.json --out OUT_DIR [--theme NAME]`. Needs a headless Chrome/Chromium (`$CARD_NEWS_CHROME` or the default macOS/Linux locations) and Pillow for the PDF. Exit 0 = clean, 2 = rendered with QA problems, 1 = spec/render error.
6. **QA** — read `OUT_DIR/qa.json` (overflow, safe-area, overlap, font fallback, image load/size per card). The probe cannot see faces, so build a contact sheet (all cards, 4 per row) and run a vision ship-gate that lists only blockers: readable face under text, head straddling the copy edge, head sliced by a frame edge, orphan word, clipped element, muddy card, consecutive near-duplicates, leftover line/pill/counter. Then check the densest cards at 375 px (phone feed width) for small text (compare boxes, step numerals, captions). Fix the spec (`focus`/`zoom`/photo swap/shorter copy) or the template and re-render; don't hand-edit PNGs.
7. **Deliver** — attach the PNGs (and the PDF for LinkedIn), name the spec path as the editable source, say which cards are draft vs final, and name the next step (approval → `publish-sns`).
8. **Clear the people in the photos** (iron rule 6) — before or together with the vault handoff. Pass the decision text to `vault_handoff.py --consent` (or edit `## 사진과 동의` afterwards); if a notice is needed, write the `KakaoTalk - …` note next to it and link both ways. The rendered set is not publishable until the notice has been posted and the waiting period the note states has passed.
9. **File it in the vault** (after the user says the set is good; the vault's AGENTS.md wants the layout shown and approved first) — `python3 scripts/vault_handoff.py SPEC.json --out OUT_DIR --title "제목" --channel instagram --source-url URL --source "[[근거 노트]]" --caption-file caption.md --consent "사진·동의 상태" [--dry-run]`. It refuses a set whose `qa.json` has problems, then writes in the vault's required order: `Attachments/<date> - <title> (카드뉴스)/` (PNGs, PDF, `cards.json` + `assets/`, `MANIFEST.md` with SHA-256 per file) → one `Content/<Channel>/<Channel> - <title>.md` (`type: channel_pack`, `status: draft`, per-card copy, embeds, caption draft, consent status, editorial notes) → one line each in `Content/INDEX`, the channel INDEX and `Attachments/INDEX` (section `## 카드뉴스` / `## 공식 콘텐츠 자료`, `updated` bumped). Existing notes are never overwritten (`"status": "exists"`), publish fields are never invented, signed URLs are rejected. Run `--dry-run` first and paste the plan; then verify with the Obsidian CLI: `obsidian eval "code=(async()=>{…unresolvedLinks…})()"` must return `[]` for the note and the three INDEXes. The vault is git-tracked but the user commits it — don't.

## Outputs

```
OUT_DIR/
├── 01.png … NN.png   1080×1350 (4:5), one per card — Instagram/Threads upload order
├── cards.pdf         all cards, for the LinkedIn document post
├── html/NN.html      rendered pages (debugging / manual tweaks)
└── qa.json           per-card probe + problems list
```

## Where things live (so the skill and the vault don't fight)

- **How** (renderer, template, themes, this procedure, tests) → this skill in `donggu-skills`, mirrored to the live clone the profiles symlink. The vault's rule: process belongs to skills, the vault keeps sources, direction, editorial judgement and the manuscripts.
- **What / why** (the set itself) → the vault area that owns the channel: Beyond Deploy official content under `FDE 커뮤니티 (Beyond Deploy)/Content/<Channel>/` + `Attachments/`; the user's personal channels under `Personal Branding/40_Channel_Packs/<Channel>/` (pass `--area "Personal Branding"` only after checking `_GUIDES/RULES.md` — the handoff currently knows the BD layout). One manuscript per channel folder; another channel reusing the set links the first note instead of copying the copy.
- `examples/sample-bd.json` is a renderer fixture, not the content's source of truth; the vault note + its `cards.json` copy are.

## Platform notes (details and official-doc caveats in `references/platform-specs.md`)

- LinkedIn document post: PDF ≤100 MB / ≤300 pages; the document can't be edited after posting — finish QA first.
- Instagram app: up to 20 items, 1.91:1–3:4; Content Publishing API: max 10 items, JPEG ≤8 MB, 4:5–1.91:1. 4:5 is the common safe value, which is why the template is 1080×1350.

## Pitfalls

- A flex/grid child can swallow the header and footer if the card wrapper loses its `type-*` class — the probe flags this as `layout`/`overlap`; fix the template, don't patch the PNG.
- "Exports PDF/PPTX" from other tools ≠ editable text; this skill's PDF is also image-per-page by design (LinkedIn renders it as a carousel), so the JSON spec is the editable source, not the PDF.
- Overseas SaaS generators (Gamma, PostNitro, aiCarousels) are fine for one-offs but must be proven with real Korean copy first; 망고보드/미리캔버스 are font-safe but tilt toward a public-notice look. See `references/tool-landscape.md` before recommending any of them.
- Mobbin has no card-news templates — it indexes shipped-UI screenshots; use it only for layout references.
- `object-position` alone can't zoom; that's what `zoom` (CSS `transform: scale`, anchored at `focus`) is for. A crop that "beheads" someone at the top edge usually needs a lower `focus` y, not more zoom.
- The cinematic scrim follows the copy: transparent 300 px above the first line, ~0.86 × overlay at the first line, full overlay below. Heads in that 300 px fade are the risky zone — keep them above it or under the copy.
- The cover is special-cased so it stays exactly the cover the user approved (own gradient, no follow-the-copy scrim, same text position). Verify a cover change with a pixel diff of a type-free strip against the last approved render, not by eye.
- Asking the host "당사자 OK 받았어?" is a dead end — the host expects the skill to decide from the policy and prepare the notice (2026-10-25: "그건 채널에 스킬 처리할수있지않나"). The policy record, not a conversation, is the evidence.
- Vision models misidentify the same person across photos and miss backs of heads; when the gate keeps flagging a "duplicate" or "head under text", label the faces once (boxes + F0/F1 tags on the source photos) and ask who is who before re-cropping.
- `.compare` columns (classic) stretch to equal height with content vertically centred; on a wash the left box is 62 % white so it doesn't read as a white sticker. In cinematic both boxes are 78 % dark, the right one outlined in the on-dark accent.
- Band dissolve: the fade must land on floor/chairs/wall, never through bottles, laptops, hands or a name tag — it reads as a smear, not a dissolve. Tune `focus`/`zoom` first (push the clutter below the band), then `fade`. If an object physically sits in the bottom 15 % of the frame it cannot be cleared; pick another frame or accept a soft veil (a veiled name tag is fine — it keeps the name unreadable).
- Wash tint: grey over a photo reads as dirt; the template pulls the blurred photo toward the accent hue (`mix-blend-mode: color`) and tints the cover layer with `accent_soft`. Check the wash at 375 px — what looks green at 1080 can collapse to grey in the feed.
- Same person on adjacent cards is a blocker. Two swipes apart is acceptable when the set has only 3–4 photos, but change the scale or side of the frame so it doesn't read as a repeat.
- Don't duplicate one photo across two cards at different crops unless the set has fewer photos than image cards; it reads as filler.
- Prior deep research on this class lives in the user's Downloads (`카드뉴스_제작방식_딥리서치_*.md`); its conclusions are condensed in `references/tool-landscape.md` — extend, don't redo.

## Verification

- `qa.json` → `problems: []`, `font_available: true` on every card, `cards_total` equals the number of PNGs on disk, `cards.pdf` present.
- Contact sheet passed the vision ship-gate (no blockers) and the densest cards read at 375 px.
- Vault handoff: dry-run plan matches, `MANIFEST.md` hashes equal the files on disk, no `supabase.co`/signed URL in the copied spec, Obsidian CLI reports zero unresolved links for the note and the three INDEXes.
- Tests: `python -m pytest tests/test_make_card_news.py` from the repo root (renders the sample when Chrome is available; the handoff tests run against a temp vault).
