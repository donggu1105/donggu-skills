---
name: make-insta-card-news
description: Use when the user asks for 카드뉴스, an Instagram carousel, 인스타 캐러셀, SNS card images, or turning a post/article into card images — especially when a DESIGN.md (getdesign.md format) or a designs/ folder should drive the look, or when cards need background/inset photos. Also use for a blog hero/대표이미지 in the same brand look.
---

# make-insta-card-news

Turn a post (.md / Obsidian Instagram pack / any text) into an Instagram card-news PNG set (1080×1350, 4:5) in a **brand look defined by a DESIGN.md**. Render = HTML template + Playwright screenshot. Text is never "drawn" by an image model — Korean stays typeset (zero typos is the goal).

**Core split: workflow (this skill, fixed) vs look (DESIGN.md, swappable).** When taste changes, swap the DESIGN.md only — never touch the skill.

## Workflow

### 1. Intake
- **Content**: source .md. An Obsidian Instagram pack may already define the card breakdown — honor it.
- **DESIGN.md**: look for `./DESIGN.md` → `./designs/*/DESIGN.md`. If absent, ask the user: getdesign catalog (`npx getdesign@latest add <name>`) / paste a brand spec / default Korean card style (proceed on kr-card-principles.md alone).
- **Count**: default cover + 3–5 body + CTA, unless specified.
- **Images?** If the content is product/tutorial/news, or the DESIGN.md is photography-forward, ask once whether the user has photos/screenshots. See **Images** below.

### 2. Page plan
Cover = one hook. Body card = **one idea per card**. Last = CTA (profile link/blog). Assign one skeleton from layout-recipes.md per card. Show the plan first if the user wants review.

### 3. DESIGN.md → card CSS (hard rules)
- **Tokens → `:root` variables.** Never inline a hex the DESIGN.md tokenizes.
- **Scale type up**: DESIGN.md px are web-scale. On a card (1080px reads ~400px on a phone) keep the hierarchy/ratios but raise absolute sizes ×1.4–2 (display 80→112–160px, body 16→28–36px). Body never below 28px.
- **Do's/Don'ts are constraints, not suggestions.** "No gradient", "radius 0" — violating one fails the deck. Apply cover→CTA.
- **Korean correction required**: apply kr-card-principles.md (font substitution, `word-break: keep-all`, UPPERCASE only on Latin labels).
- If a photography-driven system has no photo, fall back to its typographic/surface/hairline grammar and tell the user the gap in one line. Don't scrape arbitrary web images.

### 4. Images (optional) — REQUIRED READ when adding photos
Read image-handling.md. Three non-negotiables: the image is **relevant to the topic** (keyword-sourced, never random/decorative), text on it stays **legible** (scrim overlay + subject-safe placement + thumbnail test), and it's a **local downloaded file** in `assets/` (not a remote hotlink). Full-bleed background vs framed image well per the DESIGN.md mood.

### 5. Build
Copy `card-template.html` into the task folder (`<project>/cardnews-<slug>/` or /tmp) → fill `:root` tokens → add `<section class="card" id="card-N">` per card in `<!-- CARDS_HERE -->`. Custom CSS beyond the template's classes goes in one task block.

### 6. Render
```bash
cd <task> && python3 -m http.server 8765 &
```
Open `http://localhost:8765/index.html` with Playwright. If cards use images, wait for load (`waitForLoadState('networkidle')` + short timeout) before shooting. **Element screenshot per card** (`#card-N` → `card-N.png`) — viewport size is irrelevant; a 1080×1350 node exports at exactly that. Stop the server when done.

### 7. QA & deliver
Read the rendered PNGs: Korean font applied? overflow / footer collision? DESIGN.md Don'ts respected? For photo cards, run the 360px thumbnail legibility test. Report: output path + which DESIGN.md + any deliberate gap. Upload to Discord with the bot token on request.

## Hard Rules
- `word-break: keep-all` on every text container.
- Footer pinned with flex column + `margin-top: auto` — never absolute (collides with growing content).
- Emoji/pictograms only as accents, and only if the DESIGN.md allows decoration (a no-decoration system like BMW uses none).
- Text never sits on a raw photo — scrim or image well (image-handling.md).
- Never start from a blank HTML; copy the seed template.

## Files
- `card-template.html` — verified seed (token slots + card boards + footer pattern + `.bg`/`.scrim`/`.img-well` classes)
- `kr-card-principles.md` — Korean / Korean-card-news corrections (font table, size hierarchy, conventions)
- `layout-recipes.md` — 5 card skeletons (cover / numbered / rows / quote / cta)
- `image-handling.md` — photos inside cards: stock-vs-real sourcing, text legibility, placement, Playwright loading
- `pexels_fetch.py` — fetch a topic-relevant stock photo from Pexels (generic concepts)
- `commons_fetch.py` — fetch a real image of a named subject from Wikimedia Commons (specific real things)
- `supabase_upload.py` — upload a rendered card set to Supabase Storage at a dated/ordered path (`<channel>/<YYYY>/<MM-DD>/<slug>-<HHMMSS>/<NN>.png`), returns public URLs in carousel order (for Instagram Graph API hand-off). Needs `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`.
