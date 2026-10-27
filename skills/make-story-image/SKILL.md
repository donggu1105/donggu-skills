---
name: make-story-image
description: Use when the user wants 스토리 / an Instagram story image (1080×1920) — a 1–5 frame set cut from a brief, a card-news set or finished copy. Renders a JSON frame spec to story PNGs + publish JPEGs with headless Chrome, runs safe-zone QA, marks where the native link sticker goes. Does not write the copy (writing-social-content) and does not publish (publish-sns).
---

# make-story-image

Turn approved copy into Instagram story frames (1080×1920, 9:16): one hero graphic in the upper band, headline-class copy below it, and an empty lower third that the host fills with the **native link sticker** in the Instagram app. Text stays text (HTML/CSS → Chrome screenshot) so a fix is a spec edit and a re-render.

## When to use

- "스토리에도 올리자", "스토리용으로 잘라줘", a story cut of a card-news set, a one-frame event reminder.
- Not for: carousel/feed images (`make-card-news`), the copy itself (`writing-social-content`), posting (`publish-sns`).

## Iron rules

1. **A story image can't link.** Only the link sticker placed in the app links; comments don't tap, captions don't exist on stories, URLs in the image are dead text. Reserve the lower third for the sticker (`sticker` field) and never print a URL or a click verb — the validator refuses both.
2. **The sticker guide is review-only.** `NN.png` carries a faint dashed guide ("여기에 링크 스티커를 올려요"); `NN.jpg` is rendered without it and is the only file that goes to the account. Never hand the guide version to a publish path.
3. **Safe zones are hard limits.** Top 250 px (profile row, progress bar) and bottom 340 px (reply bar) hold nothing that must be read; `qa.json` fails `safe-top` / `safe-bottom` when copy crosses them.
4. **Graphic owns the upper band, copy sits on the theme background below it** (`image.mode: "top"`, default). Orange-on-orange was the first thing the ship-gate caught: coloured headline text over the coloured part of a hero graphic. Keep the accent lines of the copy on flat background; `mode: "full"` (photo behind everything) is for real photos with a dark scrim, not for product renders.
5. **Fix the asset, not the layout, when the render has a baked-in stage.** The FDE톤 capsule came with a hard-edged plinth: a layout fade can't hide a straight edge. Mask the object (geometric pill/ellipse mask fitted to the silhouette, not a colour-difference mask — that eats the dark edge pixels and leaves a fringe), fill the rest with the background colour sampled **beside** the object (the top of a render is often a different dark), and add a radial glow centred on the object so it bleeds above and below. See `references/asset-cleanup.md`.
6. **One idea per frame, ≤ 40 chars of headline.** A story is read for ~2 s. The hook frame carries the one line that stops the thumb; the CTA frame carries date/terms + the sticker zone. Three frames is the practical maximum for a promo.
7. **Copy is locked before layout** and **faces are a liability** exactly as in `make-card-news` rules 1, 5, 6 — reuse its clearance procedure for people in photos.
8. **Count before you report.** "N장" = `NN.jpg` files on disk; `qa.json` is the evidence.
9. **Production ≠ publishing.** Deliver the JPEGs and the spec path, stop. Publishing goes through `publish-sns` (`instagram` + `operation: story`) after explicit approval — and the sticker still has to be added by the host in the app before the story is worth posting (see "Publish paths").

## Procedure

1. **Frame** — source (card-news set, event note, brief), theme (`beyond-deploy`, `donggu`, or a project theme such as FDE톤's `fdethon.json`), and the frame plan: usually `hook` + `cta`, optionally one `detail`.
2. **Pick the hero per frame** — one asset each, copied next to the spec (`assets/`). Prefer the set's existing key visuals (the card-news `assets/`). For renders with a floor/plinth, run the cleanup in `references/asset-cleanup.md` first and save `*-story.jpg`. Shift the object inside the canvas (paste onto a same-size background) rather than cropping, so the handle pill at top-left and the copy block stay clear of it.
3. **Write the spec** — `examples/sample-story.json`. Fields: `references/story-spec.md`. `**bold**` = accent highlight; `\u00a0` for Korean phrase glue.
4. **Render** — `terminal(command="python3 scripts/render_story.py SPEC.json --out OUT_DIR [--theme NAME|path.json]")`. Exit 0 clean, 2 = rendered with QA problems, 1 = spec/render error. Themes resolve from this skill's `themes/` or `make-card-news/themes/`, or a `.json` path (project themes live next to the spec).
5. **QA** — read `OUT_DIR/qa.json` (`problems: []`, `font_available`, `jpeg_bytes` ≤ 8 MB). Then a contact sheet of the publish files (`NN-clean.png` / `NN.jpg`) through `vision_analyze` as a ship-gate that lists only blockers: illegible text, accent text over the accent part of the graphic, hard seam at the band, clipped hero at the top edge, handle pill crossing the hero, frame reading unfinished. Re-check at full resolution before acting on a thumbnail finding (a 400 px thumbnail reported the handle pill as missing; it was there).
6. **Deliver** — attach `NN.png` (guide version, so the host sees where the sticker goes) and name the `NN.jpg` publish files and the spec path. Say which frame is the sticker frame.
7. **File in the vault** — a story is part of the campaign note, not its own note: add a `## 스토리` section to the channel note that owns the campaign (e.g. `Content/Instagram/Instagram - <title>.md`) with the frame copy and the embeds, and copy the publish files + spec into the same `Attachments/<date> - <title> (카드뉴스)/story/` folder (`MANIFEST.md` updated with SHA-256). Use `make-card-news/scripts/vault_handoff.py` only for a standalone story set.

## Publish paths (choose one, say which)

- **A. Host posts in the app (links work).** Send the host `NN.jpg`; they add the link sticker (and optionally the "share post to story" sticker) and post. This is the only path that yields a tappable link. Default for any recruiting/registration story.
- **B. API publish via `publish-sns`** (`channel: instagram`, `operation: story`, `payload: {image_url, account}`). The Graph API posts the image only — no stickers, no link, no caption, and story media can't be edited after posting. Use it for reminders/recaps where the link lives in the profile, never for "참가 신청" frames. 24 h lifetime; the ledger keeps the story id.

## Outputs

```
OUT_DIR/
├── 01.png … NN.png        1080×1920 review frames (sticker guide visible on sticker frames)
├── 01-clean.png …         publish frames without the guide (only for frames that have a `sticker`)
├── 01.jpg … NN.jpg        publish JPEGs (what Instagram's API and the app get)
├── html/NN.html           rendered pages
└── qa.json                per-frame probe + problems + safe-zone constants
```

## Pitfalls

- `backdrop-filter` renders in headless Chrome; the handle pill is real. Thumbnails hide it — verify at full res.
- A render's top rows are often a *different* dark than its sides; sample the background next to the object or the fill shows a tonal step.
- A colour-difference mask on a chrome object drops the darkest edge pixels and leaves a dark fringe; a geometric mask fitted by PCA (axis + end circles + a 4-px grid search on radius/offset) hugs the silhouette.
- Don't rely on `zoom`/`focus` to push a plinth out of frame — it also pushes the hero into the top safe zone. Edit the asset.
- Instagram re-encodes PNG to JPEG; the renderer already writes JPEG (quality 92 → 80 until ≤ 8 MB) so what you review is what posts.
- Mentions/hashtags typed into the image are not stickers; they don't link either.

## Verification

- `qa.json` → `problems: []`, `frames_total` equals the number of `NN.jpg` files, every `jpeg_bytes` ≤ 8 388 608.
- Ship-gate vision pass on the publish frames returned SHIP (no blockers).
- Tests: `python3 -m unittest tests.test_make_story_image -q` from the repo root (spec validation + a render when Chrome is available).
