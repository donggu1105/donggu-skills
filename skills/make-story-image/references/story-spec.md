# Story spec

```json
{
  "theme": "beyond-deploy",            // theme name (this skill or make-card-news themes/) or "path/to/theme.json"
  "handle": "beyonddeploy.kr",         // small top-left signature; theme.handle is the default
  "backdrop": { "src": "assets/x.jpg" },   // optional set-wide fallback image
  "frames": [ ...1–5 frames... ]
}
```

## Frame

| field | type | limit | notes |
|---|---|---|---|
| `type` | `hook` \| `detail` \| `cta` | — | `cta` pulls the copy block down toward the sticker zone |
| `kicker` | string | 28 chars | accent colour, one line (date, series) |
| `title` | string | 40 chars (excl. `\n`) | required; `**…**` = accent highlight; `\n` = line break |
| `body` | string | 90 chars | optional, one or two lines |
| `sticker` | string | 24 chars | label for the link-sticker slot; makes this a sticker frame (review guide + `-clean` publish render) |
| `image` | object | — | `src` (local path), `mode` `top` (default) \| `full`, `band` px (mode top, default 1000), `focus`, `zoom`, `overlay` (mode full) |

Refused by the validator: more than 5 frames, remote `image.src`, a URL / `.kr` / `.com` / click verb (클릭·눌러·탭·터치) in any text field, fields over their limits.

## Geometry (1080×1920)

- safe top 250 px, safe bottom 340 px (`qa.json` → `safe`)
- handle pill at top + 340 px; copy block bottom at 1920 − 340 − 300 (hook/detail) or − 270 (cta, mode top)
- sticker slot: 150 px tall, bottom at 1920 − 340 − 60 → y 1370–1520
- mode top: graphic band `band` px tall from the top, fades into the theme background over its last ~40 %
