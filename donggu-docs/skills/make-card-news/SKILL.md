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
3. **Every set carries images, and body type is headline-sized.** Dark-mode variants were considered and declined for Beyond Deploy (white + olive is the brand); don't offer them again unless asked. A text-only white set was rejected as "너무 별로". Default rhythm: cover `full` photo → hook `full` photo → white content card → `band` card → … → closing `band`/`inline`. Body copy stays at the template sizes (≥48 px); if it doesn't fit, cut words, never shrink type.
4. **One cover, then one atmosphere.** The cover is the only dark full-bleed card. Everything after it sits on the set `backdrop` wash (text cards) or dissolves into its own blurred photo (band cards) — never flat white next to a photographic cover, and never a second dark cover at card 2 (it reads as two covers, then an abrupt switch). The closing card sits on the plain wash so it lands instead of looking like one more slide.
5. **Faces are a liability, not decoration.** Prefer frames where people are seen from behind, in profile, or small in a wide room. Never crop a head at an edge, never put the series pill on a face (band cards place it below the photo for this reason), and don't use a close-up of an identifiable participant without their OK. `focus`/`zoom` exist to steer crops away from faces, not into them.
6. **Count before you report.** Say "N장" only after listing the output directory — PNG files, not spec or HTML files. `qa.json` is the evidence.
7. **Production ≠ publishing.** Deliver files and the source path, state draft/final, stop. Publishing goes through `publish-sns` after the user's explicit approval.
8. **No fake buttons.** Nothing inside a card image is tappable — Instagram carousels have no in-image links, and LinkedIn disables links inside document PDFs. The closing `cta` is a sentence with an arrow, never a pill/button, never a URL, never "클릭/눌러/탭". Point to a native action instead (저장, 공유, 댓글, 프로필 링크, 첫 댓글) and hand the URL to the caption via `writing-social-content`. The validator rejects URLs and click verbs in `cta`.
9. **Korean first.** The template uses `word-break: keep-all`; the QA probe confirms the primary font actually loaded. Fix orphans with a non-breaking space in the spec (`100여\u00a0명`) or a manual `\n`, not by shrinking fonts below the template sizes.

## Procedure

1. **Frame** — content type (회차 홍보 / 후기·필드노트 요약 / 인사이트 / 개인 글), target platform(s), theme (`beyond-deploy` for Beyond Deploy content, `donggu` for the user's personal channels, or a new `themes/<name>.json`), and the approved source text.
2. **Outline per card** — 7–9 cards: cover → hook (quote or point) → **stat** (one number + one line, the second hook) → 2–4 content cards (point / list / compare / steps, one claim each) → closing with one CTA. The first three cards must each stop a reader who has no context — Instagram re-serves card 2 and 3 as fresh posts, and LinkedIn's 2026 feed test shows cards 1–2 side by side. Never make every card the same bullet list. Card types and field limits: `references/card-spec.md`.
3. **Pick images** — download/copy them next to the spec (`assets/`), JPEG/PNG/WebP ≥ 1080 px wide, under ~400 KB each after resizing. Per card choose `mode`: `full` (photo fills the card, dark gradient, white type — cover and hook), `band` (photo in the top 500 px, text below — content cards), `inline` (rounded image between title and body — illustrations). Set `focus` (CSS object-position, e.g. `"50% 30%"`) and optional `zoom` (1–2) so no head touches an edge; set `overlay` 0.7–0.85 on `full` so white text clears busy areas. Remote URLs are refused on purpose — fetch first so the set is reproducible.
4. **Write the spec** — JSON as in `examples/sample-bd.json`. `series` is the header label, `handle` the footer. `**bold**` inside text becomes an accent highlight; `\n` is a line break; nothing else is markup.
5. **Render** — `python3 scripts/render_cards.py SPEC.json --out OUT_DIR [--theme NAME]`. Needs a headless Chrome/Chromium (`$CARD_NEWS_CHROME` or the default macOS/Linux locations) and Pillow for the PDF. Exit 0 = clean, 2 = rendered with QA problems, 1 = spec/render error.
6. **QA** — read `OUT_DIR/qa.json` (overflow, safe-area, overlap, footer position, font fallback, image load/size per card). The probe cannot see faces or dead space, so build a contact sheet (all cards, 4 per row) plus a strip of the band crops (top 620 px of each band card) and inspect them with the runtime's vision capability as an art director would: heads clear of every edge, pill not on a person, white text legible on every `full` card, body type reading as big as a headline, no card ending with an empty bottom third, cards 1 and 2 sharing one accent language. Fix the spec (`focus`/`zoom`/photo swap/shorter copy) or the template and re-render; don't hand-edit PNGs. Expect 3–5 rounds; the sample took 11.
7. **Deliver** — attach the PNGs (and the PDF for LinkedIn), name the spec path as the editable source, say which cards are draft vs final, and name the next step (approval → `publish-sns`). For Beyond Deploy, copy final assets next to the content note in the vault.

## Outputs

```
OUT_DIR/
├── 01.png … NN.png   1080×1350 (4:5), one per card — Instagram/Threads upload order
├── cards.pdf         all cards, for the LinkedIn document post
├── html/NN.html      rendered pages (debugging / manual tweaks)
└── qa.json           per-card probe + problems list
```

## Platform notes (details and official-doc caveats in `references/platform-specs.md`)

- LinkedIn document post: PDF ≤100 MB / ≤300 pages; the document can't be edited after posting — finish QA first.
- Instagram app: up to 20 items, 1.91:1–3:4; Content Publishing API: max 10 items, JPEG ≤8 MB, 4:5–1.91:1. 4:5 is the common safe value, which is why the template is 1080×1350.

## Pitfalls

- A flex/grid child can swallow the header and footer if the card wrapper loses its `type-*` class — the probe flags this as `layout`/`overlap`; fix the template, don't patch the PNG.
- "Exports PDF/PPTX" from other tools ≠ editable text; this skill's PDF is also image-per-page by design (LinkedIn renders it as a carousel), so the JSON spec is the editable source, not the PDF.
- Overseas SaaS generators (Gamma, PostNitro, aiCarousels) are fine for one-offs but must be proven with real Korean copy first; 망고보드/미리캔버스 are font-safe but tilt toward a public-notice look. See `references/tool-landscape.md` before recommending any of them.
- Mobbin has no card-news templates — it indexes shipped-UI screenshots; use it only for layout references.
- `object-position` alone can't zoom; that's what `zoom` (CSS `transform: scale`, anchored at `focus`) is for. A crop that "beheads" someone at the top edge usually needs a lower `focus` y, not more zoom.
- `.compare` columns stretch to equal height with content vertically centred; on a wash the left box is 62 % white so it doesn't read as a white sticker.
- Band dissolve: the fade must land on floor/chairs/wall, never through bottles, laptops, hands or a name tag — it reads as a smear, not a dissolve. Tune `focus`/`zoom` first (push the clutter below the band), then `fade`. If an object physically sits in the bottom 15 % of the frame it cannot be cleared; pick another frame or accept a soft veil (a veiled name tag is fine — it keeps the name unreadable).
- Wash tint: grey over a photo reads as dirt; the template pulls the blurred photo toward the accent hue (`mix-blend-mode: color`) and tints the cover layer with `accent_soft`. Check the wash at 375 px — what looks green at 1080 can collapse to grey in the feed.
- Don't reuse one frame two swipes apart (cards 5 and 7 with the same speaker read as a repeat even when not adjacent); reuse is fine between a `full` and a `band` crop of the same frame.
- Don't duplicate one photo across two cards at different crops unless the set has fewer photos than image cards; it reads as filler.
- Prior deep research on this class lives in the user's Downloads (`카드뉴스_제작방식_딥리서치_*.md`); its conclusions are condensed in `references/tool-landscape.md` — extend, don't redo.

## Verification

- `qa.json` → `problems: []`, `font_available: true` on every card, `cards_total` equals the number of PNGs on disk, `cards.pdf` present.
- Contact sheet + band strip inspected visually: no head cut by an edge, no pill on a face, no clipping/overlap/mid-word breaks, no empty bottom third.
- Tests: `python -m pytest tests/test_make_card_news.py` from the repo root (renders the sample when Chrome is available).
