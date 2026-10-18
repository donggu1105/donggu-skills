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
2. **Text is never baked into generated images.** Illustrations (if any) come from user assets or `get-ai-image`; all words are rendered by the template so they stay editable and legible.
3. **Count before you report.** Say "N장" only after listing the output directory — PNG files, not spec or HTML files. `qa.json` is the evidence.
4. **Production ≠ publishing.** Deliver files and the source path, state draft/final, stop. Publishing goes through `publish-sns` after the user's explicit approval.
5. **Korean first.** The template uses `word-break: keep-all`; the QA probe confirms the primary font actually loaded. Fix orphans with a non-breaking space in the spec (`100여\u00a0명`) or a manual `\n`, not by shrinking fonts below the template sizes.

## Procedure

1. **Frame** — content type (회차 홍보 / 후기·필드노트 요약 / 인사이트 / 개인 글), target platform(s), theme (`beyond-deploy` for Beyond Deploy content, `donggu` for the user's personal channels, or a new `themes/<name>.json`), and the approved source text.
2. **Outline per card** — 6–8 cards: cover → hook (quote or point) → 2–4 content cards (point / list / compare / steps, one claim each) → closing with one CTA. Never make every card the same bullet list. Card types and field limits: `references/card-spec.md`.
3. **Write the spec** — JSON as in `examples/sample-bd.json`. `series` is the header label, `handle` the footer. `**bold**` inside text becomes an accent highlight; `\n` is a line break; nothing else is markup.
4. **Render** — `python3 scripts/render_cards.py SPEC.json --out OUT_DIR [--theme NAME]`. Needs a headless Chrome/Chromium (`$CARD_NEWS_CHROME` or the default macOS/Linux locations) and Pillow for the PDF. Exit 0 = clean, 2 = rendered with QA problems, 1 = spec/render error.
5. **QA** — read `OUT_DIR/qa.json` (overflow, safe-area, overlap, footer position, font fallback per card), then look at the first card and the densest card with the current runtime's image/vision capability: Korean line breaks on word boundaries, nothing clipped, nothing in the bottom 10 % where platform UI sits, accent used sparingly. Fix the spec or theme and re-render; don't hand-edit PNGs.
6. **Deliver** — attach the PNGs (and the PDF for LinkedIn), name the spec path as the editable source, say which cards are draft vs final, and name the next step (approval → `publish-sns`). For Beyond Deploy, copy final assets next to the content note in the vault.

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
- Prior deep research on this class lives in the user's Downloads (`카드뉴스_제작방식_딥리서치_*.md`); its conclusions are condensed in `references/tool-landscape.md` — extend, don't redo.

## Verification

- `qa.json` → `problems: []`, `font_available: true` on every card, `cards_total` equals the number of PNGs on disk, `cards.pdf` present.
- Two cards inspected visually (first + densest) with no clipping, overlap or mid-word breaks.
- Tests: `python -m pytest tests/test_make_card_news.py` from the repo root (renders the sample when Chrome is available).
