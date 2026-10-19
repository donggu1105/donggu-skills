# Card spec

One JSON file per card set. Top level:

| Key | Required | Meaning |
|---|---|---|
| `theme` | no (default `donggu`) | theme name in `themes/` or a path to a `.json` |
| `series` | no | header label, e.g. `Beyond Deploy · 필드노트` |
| `handle` | no (theme default) | footer label, e.g. `beyonddeploy.kr`, `@100x.donggu` |
| `source` | no | where the copy came from (kept for provenance, not rendered) |
| `cards` | yes | ordered list, 1–20 cards (6–8 recommended) |

## Card types

| `type` | Required | Optional | Use for |
|---|---|---|---|
| `cover` | `title` | `kicker`, `subtitle` | card 1 — the hook, ≤ 3 title lines |
| `point` | `title`, `body` | — | one claim + 2–4 sentences |
| `quote` | `quote` | `who` | a question or line heard verbatim |
| `list` | `title`, `items` (≤5) | `lead` | parallel items, bullets |
| `steps` | `title`, `items` (≤5) | `lead` | an ordered process, numbered badges |
| `compare` | `title`, `left{title,body?}`, `right{title,body?}` | `footer` | before/after, A vs B — the right box is the accented one |
| `closing` | `title` | `body`, `cta` | last card — one CTA pill, no like/follow begging |

Limits enforced by `validate_spec`: unknown type, missing required field, >5 items, title > 60 chars, bad `image` object.

## `image` (optional on every type; `compare` accepts `full`/`band` only)

| Key | Required | Meaning |
|---|---|---|
| `src` | yes | local `.jpg/.jpeg/.png/.webp`, absolute or relative to the spec file. URLs are rejected — download first |
| `mode` | no (default `band`) | `full` = fills the card behind a dark gradient, white type, text bottom-anchored · `band` = top 500 px, series pill moves below the photo · `inline` = 340 px rounded image after the title (point/list/steps) or after the body (cover/quote/closing) |
| `focus` | no (`50% 50%`) | CSS `object-position`; also the zoom anchor. Lower the y value to give heads headroom |
| `zoom` | no (1.0) | 1–2, crops in around `focus` |
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
- Title and quote 80 px/1.18 (72 px on `band` cards); body 54 px (48 on band); list/steps items 52 px (42 on band); lead/sub 42 px; compare column body 40 px, closing line 42 px; series pill 26 px; footer 26 px. Everything the reader is meant to read is ≥ 40 px — headline-sized by design.
- White cards start their content at a fixed line (170 px under the pill) so the set keeps one rhythm; `full` cards bottom-anchor the text above the footer; `band` cards start right under the pill below the photo.
- Body boxes cap at 400–700 px tall and clip (`overflow: hidden`); the QA probe reports `overflow` when that happens — shorten the text, never the type.

## Themes (`themes/<name>.json`)

`fonts` (first = QA-checked), `bg`, `ink`, `muted`, `accent`, `accent_soft`, `line`, `surface`, `handle`, optional `lang`.
`beyond-deploy` mirrors the BD mail design (white, olive `#4d7c0f`, ink `#1e2b21`); `donggu` is the personal-channel look. Add a theme instead of overriding colors in a spec.
