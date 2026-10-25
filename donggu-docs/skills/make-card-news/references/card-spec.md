# Card spec

One JSON file per card set. Top level:

| Key | Required | Meaning |
|---|---|---|
| `theme` | no (default `donggu`) | theme name in `themes/` or a path to a `.json` |
| `layout` | no (default `classic`; samples use `cinematic`) | `cinematic` = every card is a full-bleed photo with a dark scrim behind the copy and white type; no top bar, footer rule, series pill or page counter; the handle shows small on the first and last card only. Every card needs `image` or a set `backdrop`. `classic` = the older white/wash/band look with header pill and footer |
| `series` | no | header pill label (classic only), e.g. `Beyond Deploy · 필드노트` |
| `handle` | no (theme default) | footer label (classic: every card; cinematic: first and last card), e.g. `beyonddeploy.kr`, `@100x.donggu` |
| `source` | no | where the copy came from (kept for provenance, not rendered) |
| `cards` | yes | ordered list, 1–20 cards (6–8 recommended) |
| `backdrop` | no | cinematic: `{src, focus?, overlay?}` — the photo used for any card without its own `image`. classic: `{src, tint}` — a photo (usually the cover's or the warmest frame) rendered as a heavily blurred, brand-tinted wash behind every text card, so the set keeps one atmosphere after the cover instead of dropping to flat white. `tint` 0.5–1 = how much theme bg covers it (0.68 ≈ clearly green at phone size, 0.86 ≈ barely there). Band cards wash with their own photo; `full` cards never wash; a card can opt out with `"wash": false` |

Examples: `examples/sample-bd.json` (cinematic, the default look) and `examples/sample-bd-classic.json` (classic, kept as a regression fixture).

`vault_handoff.py` copies the spec into the set folder (`Content/CardNews/<date> - <title>/cards.json`) with `image.src`/`backdrop.src` rewritten to `assets/<file>` and any signed URL in `source` removed — edit that copy and re-render from there.

## Card types

| `type` | Required | Optional | Use for |
|---|---|---|---|
| `cover` | `title` | `kicker`, `subtitle` | card 1 — the hook, ≤ 3 title lines |
| `stat` | `value` (≤ 6 chars), `label` | `kicker`, `unit`, `context`, `source` | one number per slide — the second hook (card 2–3); `value` is the digits only, `unit` the counter (`여 명`, `%`, `배`), `label` a headline-sized sentence, `source` where the number comes from |
| `point` | `title`, `body` | — | one claim + 2–4 sentences |
| `quote` | `quote` | `who` | a question or line heard verbatim |
| `list` | `title`, `items` (≤5) | `lead` | parallel items, bullets |
| `steps` | `title`, `items` (≤5) | `lead` | an ordered process, numbered badges |
| `compare` | `title`, `left{title,body?}`, `right{title,body?}` | `footer` | before/after, A vs B — the right box is the accented one |
| `closing` | `title` | `body`, `cta` | last card — `cta` is one platform-native action line (저장 / 공유 / 댓글 / "링크는 프로필과 첫 댓글에"), rendered as an accent line with an arrow, **not a button**. URLs and click/tap verbs are rejected: nothing inside the image is clickable on Instagram, and LinkedIn strips links from document PDFs. The real link goes in the caption / first comment / profile |

Limits enforced by `validate_spec`: unknown type, missing required field, >5 items, title > 60 chars, stat value > 6 chars, bad `image` object.

## `image` (optional on every type; `compare` accepts `full`/`band` only)

| Key | Required | Meaning |
|---|---|---|
| `src` | yes | local `.jpg/.jpeg/.png/.webp`, absolute or relative to the spec file. URLs are rejected — download first |
| `mode` | no (default `band`) | `full` = fills the card behind a dark gradient, white type, text bottom-anchored · `band` = top 500 px, series pill moves below the photo · `inline` = 340 px rounded image after the title (point/list/steps) or after the body (cover/quote/closing) |
| `focus` | no (`50% 50%`) | CSS `object-position`; also the zoom anchor. Lower the y value to give heads headroom |
| `zoom` | no (1.0) | 1–2, crops in around `focus` |
| `fade` | no (0.42) | `band` only, 0.2–0.9: fraction of the band height where the photo starts dissolving into the page. Raise it (0.7–0.86) when the bottom of the frame holds things that must stay sharp (hands, a laptop, a badge); the dissolve shortens accordingly |
| `overlay` | no (0.72) | 0–1 gradient darkness for `full`; 0.78–0.85 for busy or bright photos |
| `alt` | recommended | what's in the frame — used for review and for the vault note |

The probe records `images[]` (loaded, natural size) and flags `image` (failed to load) and `image-small` (< 900 px wide).

## Inline markup (the only markup)

- `**text**` → accent highlight (bold + soft underline band). Use once per card at most.
- `\n` → line break. `\n\n` → paragraph gap.
- `\u00a0` (non-breaking space) → keep a number and its unit together: `100여\u00a0명`, `24\u00a0명`.
- Everything else is escaped literally (`<`, `&`, quotes are safe).

## Sizes baked into the template (do not shrink to fit — cut copy instead)

- Canvas 1080×1350, side padding 84 px (~7.8 %), footer sits on the 90 % line; nothing below it.
- Cinematic: copy stack bottom-anchored 200 px above the bottom edge (cover keeps its approved position), cover title 88 px, other titles/quotes 100 px, stat number 260 px + unit 84 px, compare body 46 px, step numerals 40 px, kicker 30 px in `accent_on_dark`.
- Tokens in `card.html`: `--title-size` 88 px (`--title-size-band` 78 px on `band` cards), `--body-size` 58 px (52 on band), `--item-size` 56 px (46 on band), `--sub-size` 46 px for lead/sub/closing line/stat context; compare column body 44 px; stat number 300 px + unit 92 px (220/72 on band), stat label = `--title-size`; series pill 26 px; footer 26 px. Lead, sub and closing lines are set in ink, not grey — body copy is meant to read as big and as dark as a headline.
- White cards start their content at a fixed line (170 px under the pill) so the set keeps one rhythm; `full` cards bottom-anchor the text above the footer; `band` cards start right under the pill below the photo.
- Body boxes cap at 400–700 px tall and clip (`overflow: hidden`); the QA probe reports `overflow` when that happens — shorten the text, never the type.

## Themes (`themes/<name>.json`)

`fonts` (first = QA-checked), `bg`, `ink`, `muted`, `accent`, `accent_soft`, `line`, `surface`, `handle`, optional `accent_on_dark` (accent used on photos in `cinematic`; falls back to `accent_soft`), optional `lang`.
`beyond-deploy` mirrors the BD mail design (white, olive `#4d7c0f`, ink `#1e2b21`); `donggu` is the personal-channel look. Add a theme instead of overriding colors in a spec.
