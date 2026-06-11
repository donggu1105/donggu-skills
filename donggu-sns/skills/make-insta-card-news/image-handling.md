# image-handling — photos inside cards

Two placements: **full-bleed background** (photo fills the card, text sits on top) and **image well** (a framed photo inside the layout, text beside/below). Both must satisfy two non-negotiables: the image is **relevant to the content**, and text on/near it stays **legible**.

## 1. Relevance first (sourcing)

**The image must relate to the post's topic. Never random/decorative stock.** First decide **stock vs real-web** by what the card needs:

- **Generic / atmospheric concept** (developer coding, marketing, planning, AI) → **Pexels stock** (section "Keyword stock" below). A representative photo is enough.
- **A specific, named real thing** (a real place like 한강/Han River, a product, a person, a brand, a landmark, a specific app's UI, a logo, a meme, a news event) → **real web image**. A generic stock photo of "a river" is wrong when the post is about the Han River. Use:
  1. **Wikimedia Commons** — `commons_fetch.py "<subject>" <out.jpg> [width] [index]`. Free-licensed real images of named places/products/people/landmarks/logos, no key. Prints license + descriptionurl. Best first try for real subjects.
  2. **Agent web search fallback** — if Commons has nothing usable, use your own `WebSearch` for the subject, `WebFetch` a promising page to extract a direct image URL (`.jpg/.png/.webp`), then download it with `curl`/urllib (browser UA). ⚠️ web images have **unverified copyright** — surface the source URL to the user and let them decide on use/attribution, exactly like the stock-provenance step below. Prefer official press/brand pages or Wikipedia over random blogs.

Derive search terms from the topic. For real subjects, name the thing precisely ("Han River Seoul night", not "river"). **Always Read the downloaded file and confirm it's the right subject** — both Commons and web search return wrong hits (maps, diagrams, look-alikes); bump `index` / refine the query / try the other source and retry.

For generic concepts, source — in this order of preference:

1. **User-provided** — screenshot, product shot, or photo the user attaches. Least "AI-looking", always most relevant. Ask once if the content is product/tutorial/news.
2. **Keyword stock** (free, no decorative filler):
   - **Pexels API** — best automated path. Use `pexels_fetch.py "<keyword>" <out.jpg> [orientation] [index]` with `PEXELS_API_KEY` in env. It searches, picks a portrait rendition, downloads, and prints the photographer/url. **Then Read the saved file and confirm the subject matches** — keyword search is imperfect (e.g. "ui design" returned a ChatGPT screen; bump `index` or change keywords and retry). Free tier: 200/hr, 20k/mo. ⚠️ the default Python-urllib UA is 403-blocked → the helper sends a browser UA.
   - **Pexels** (manual) `pexels.com/search/<kw>/` — supports Korean keywords. First choice for local/Korean scenes.
   - **Unsplash** `unsplash.com/s/photos/<kw>` — strong for lifestyle/atmosphere; English keywords. ⚠️ license requires hotlink + attribution — but for PNG export you must **download** the file, so prefer Pexels/Pixabay/Flickr-CC for downloadable use, or credit Unsplash in a caption.
   - **Pixabay** / **Flickr CC** (`flickr.com/search/?text=<kw>&license=2,3,4,5,6,9`) — downloadable, attribution-friendly.
3. **AI-generated** — only when no real photo fits; keep it free of embedded text/logos/fake UI. (Local mflux or a cloud image API.)

Derive keywords from the topic, not the headline literally: a "솔로 개발자의 앱 출시기" → `developer desk`, `code laptop`, `seoul han river` — not `기획 디자인`.

**Download to `<task>/assets/`**, name by purpose (`assets/hero-developer-desk.jpg`, not a hash). Record source in `assets/SOURCES.md` (one line per file: `hero-developer-desk.jpg ← <url>`). Surface provenance + attribution choice to the user before finalizing.

## 2. Legibility (text over photo)

**Text never sits directly on a raw photo.** A photo's bright/busy regions kill white-text contrast (verified: white headline over a light road area is unreadable without treatment). Apply, in order:

1. **Scrim overlay** — a gradient/solid layer between photo (`z-index:0`) and text (`z-index:2`), at `z-index:1`. Weight it toward the text:
   - Text at bottom → `scrim-bottom`: `linear-gradient(to top, rgba(0,0,0,.82) 0%, rgba(0,0,0,.55) 32%, rgba(0,0,0,.12) 60%, transparent 100%)`
   - Text centered/over whole frame → `scrim-full`: solid `rgba(0,0,0,.5)` (raise to .6 over busy photos)
   - Light-mode design (dark text on photo) → invert scrim to white `rgba(255,255,255,.7)`
2. **Subject-safe placement** — read the image first (Read tool), note where the subject/face sits, place text in the quiet zone. Set `object-position` inline per image (e.g. `object-position:center 30%` for sky-heavy, `center 70%` for foreground subject) so the subject isn't cropped out on 4:5.
3. **Thumbnail test** — downscale the rendered PNG to ~360px wide; if the headline isn't readable, the scrim is too light or the photo was wrong. Fix before delivery.

If the DESIGN.md forbids scrims/overlays, use an **image well** instead (section 3) so text never overlaps the photo.

## 3. Placement patterns

**Full-bleed background** (`.card.has-bg`): photo in `.bg` (`z-index:0`, `object-fit:cover`), scrim in `.scrim` (`z-index:1`), content in `.card-pad` (`z-index:2`). Best for covers and quote cards. Text aligns to the scrim-heavy edge (usually bottom).

**Image well** (`.img-well`): a framed photo block inside the content flow — top band, side column, or inset. `object-fit:cover`, fixed aspect (`r-16x9` / `r-4x5` / `r-1x1`), corners follow DESIGN.md `--radius`. Text lives in the remaining space, so **no scrim needed** — legibility comes from separation, not overlay. Best for evidence/feature cards where the photo is content, not backdrop.

DESIGN.md decides the mood: a photography-forward brand (BMW-style) wants full-bleed; a clean editorial brand may prefer image wells with generous margins.

## 4. Rendering (Playwright)

Images must finish loading **before** the screenshot or they render blank. Serve the task folder over `python3 -m http.server` (so `assets/` resolves), then after navigate:

```js
await page.goto(url);
await page.waitForLoadState('networkidle');   // or: wait for each img.complete
await page.waitForTimeout(500);                // safety for decode
await page.locator('#card-N').screenshot({ path: 'card-N.png' });
```

Use **local downloaded files** (`assets/…`), not remote hotlinks — reproducible, and avoids a slow/blocked fetch failing the screenshot.
