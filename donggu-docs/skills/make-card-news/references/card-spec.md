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

Limits enforced by `validate_spec`: unknown type, missing required field, >5 items, title > 60 chars.

## Inline markup (the only markup)

- `**text**` → accent highlight (bold + soft underline band). Use once per card at most.
- `\n` → line break. `\n\n` → paragraph gap.
- `\u00a0` (non-breaking space) → keep a number and its unit together: `100여\u00a0명`, `24\u00a0명`.
- Everything else is escaped literally (`<`, `&`, quotes are safe).

## Sizes baked into the template (do not shrink to fit — cut copy instead)

- Canvas 1080×1350, side padding 84 px (~7.8 %), footer sits on the 90 % line; nothing below it.
- Title 72 px/1.18 (cover 92 px), body 42 px/1.55, list items 40 px, quote 56 px, compare columns 34 px, footer/meta 24–26 px.
- Body boxes cap at 720–760 px tall and clip (`overflow: hidden`); the QA probe reports `overflow` when that happens — shorten the text.

## Themes (`themes/<name>.json`)

`fonts` (first = QA-checked), `bg`, `ink`, `muted`, `accent`, `accent_soft`, `line`, `surface`, `handle`, optional `lang`.
`beyond-deploy` mirrors the BD mail design (white, olive `#4d7c0f`, ink `#1e2b21`); `donggu` is the personal-channel look. Add a theme instead of overriding colors in a spec.
