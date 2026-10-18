# Card news / carousel tool landscape

Decision input for step 1 of `make-card-news` (in-house renderer vs SaaS). Structural facts (inputs, outputs, caps, Korean support) are stable; **prices and tier limits drift — open the pricing page before quoting a number.**

## Decision table

| Need | Pick | Why |
|---|---|---|
| Recurring Beyond Deploy content, same tone every time, fix one card later | In-house HTML/CSS → headless Chromium PNG (+ PDF merge) | No subscription, Korean web fonts under our control, per-card edits, outputs for both platforms from one source |
| Fastest decent draft from a text/URL, LinkedIn + Instagram | Gamma (Social format) | Card split + theme + `ko` + PNG zip/PDF; API on paid plans |
| Korean fonts/templates and hands-on editing, no English-tool risk | 망고보드 AI 카드뉴스, 미리캔버스, Canva | Topic → multi-card draft (망고보드), template editing in Korean UI |
| Illustration-led explainer, few words per card | baoyu-xhs-images (+ image model) | 1–10 card series, style consistency from card 1; text is pixels |
| Carousel-only tool with scheduling / agent access | PostNitro | Topic/URL/thread → carousel, scheduler on mid tier, MCP/CLI/API add-on |
| Zero-commitment test | aiCarousels | No sign-up, free with watermark |

## In-house HTML/CSS path (implemented as `make-card-news`)

`scripts/render_cards.py` implements exactly this structure: per-card JSON + one template/theme + headless Chrome → PNG per card → Pillow PDF merge → probe-based layout checks (overflow, safe area, overlap, font fallback). Open-source projects reviewed before building it (none was a Korean-ready finished product):

- `roscodetech/claude-carousel` — HTML per card, Python/Playwright PNG, real layout-check routines; PNG only, English fonts, its LinkedIn `max_slides=20` is an internal setting not the platform limit.
- `jeevanbavandla/instagram-carousel-skill` — lightweight HTML card series spec with Playwright PNG and browser PNG/PDF buttons; default font Poppins.
- `threads-carousel-claude-skill` — Next.js preview with style controls; PDF is per-card JPEG via jsPDF (not selectable text); fonts Latin/Cyrillic.
- `Slashgear/linkedin-carousel-gen` — React/Satori/resvg/pdf-lib; square default; Satori path renders fonts separately from the browser preview.
- Marp CLI — Markdown → PDF/PNG with custom slide size; simplest fixed-template base.

## SaaS / AI generators

- **Gamma** (`gamma.app/ko`) — "Social" format: posts, carousels, stories, infographics sized per platform; input prompt/text/URL/doc; export PNG (per-card ZIP) or PDF (LinkedIn document); direct share to LinkedIn, Instagram via export. API: `format: social`, `cardOptions.dimensions: 4x5`, `textMode` (generate/condense/preserve), language `ko`; API keys on paid plans, generation uses credits. Use preserve mode so the model does not move the argument.
- **망고보드 AI 카드뉴스** (`mangoboard.net/AIDesigner/Cardnews`) — topic or pasted text → AI outline → multi-page cards with copy, images, design; opens in editor; platform-size conversion; free after sign-up with a daily cap. Strong Korean fonts (~1,000); showcase tone is public-sector/notice.
- **미리캔버스** — AI presentation (topic → PPT draft) exists; a card-news-specific AI generator was not found — card news is template-based hand editing. PPTX export has distinct options (single image / elements as images / editable text), so export ≠ editable by default.
- **Canva** — deepest template library, best manual control; MCP tools exist (generate/edit/export, autofill on Pro+) but new clients need developer waitlist approval — plan ≠ connection.
- **PostNitro** (`postnitro.ai/plans`, verified live) — Free: 5 downloads, watermark, 5 AI slides/carousel. Starter $15/mo: 30 downloads, 8 slides. Creator $25/mo: unlimited downloads, 15 slides, scheduling to 10 accounts, custom templates. Team $50/mo: 20 slides, 30 accounts. MCP/CLI/REST is a $10/mo add-on (250 credits; imported slide 1 credit, AI slide 2).
- **aiCarousels** — free, no sign-up, AI writes copy, LinkedIn/Instagram feed+story/TikTok sizes; watermark on free, Pro ≈ $15/mo (third-party figure).
- **Predis.ai** — carousels + captions + scheduling, credit-metered from ~$19–32/mo, no permanent free tier, catalog/e-commerce tilt — overkill for community content.
- **Bannerbear** — template-variable → image/PDF API with batch/MCP; only worth it for high-volume formulaic output.

## baoyu skill family (don't confuse)

- `baoyu-infographic` — one structured image (installed).
- `baoyu-xhs-images` — XHS = Xiaohongshu; content → 1–10 card images, 12 styles, card 1 as style anchor; text is generated pixels; Korean quality unverified.
- `baoyu-slide-deck` — per-card images merged to PDF/PPTX via `addImage`; not editable text.

## Redirects for adjacent asks (candidates, not yet checked in a session)

- Email newsletter design references: Really Good Emails, Milled.
- Device/branding mockups: Figma mockup plugins (e.g. MockupHive), Shots.so.
