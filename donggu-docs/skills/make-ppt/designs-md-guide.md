# designs-md-guide — the .md-driven path

How make-ppt turns a project's `DESIGN.md` into a deck. The `.md` files are the **standard**: a `DESIGN.md` decides the look, a content `.md` decides what's on the slides, and make-ppt synthesizes them into a single self-contained HTML deck.

This path is **additive** — it does not change frontend-slides' mood/preview discovery. Use it when a design system already exists or the user wants a specific brand/aesthetic.

## Where the DESIGN.md lives

make-ppt accepts a `DESIGN.md` in either place — it checks `./DESIGN.md` first, then `./designs/*/DESIGN.md`:

**Single design — root `./DESIGN.md`.** The getdesign CLI's default location (`npx getdesign add <name>` writes `./DESIGN.md`). Simplest; one design per project.

**Several designs — a `./designs/` library.** One subfolder per design:

```
designs/
  README.md            (optional) library readme
  <name>/
    DESIGN.md           design system spec (required)
    fonts.md            (optional) font mapping + web-font <link>
    <deck>.md           (optional) deck content
    <deck>.html         generated deck (single HTML)
```

If neither exists, obtain a `DESIGN.md` first (see below). The generated deck is written next to its `DESIGN.md` by default — unless the project keeps decks elsewhere.

## DESIGN.md — the look

A `DESIGN.md` specs a design system: colours (hex), typography (family, size, weight, letter-spacing), spacing scale, border radius, components, and **Do's / Don'ts**. It is the same kind of artifact as a `STYLE_PRESETS.md` preset — just richer, and per-project. No fixed schema; it must just be specific enough that every colour, font, and rule reads straight off it.

**To obtain one:**
- `npx getdesign@latest add <name>` — run from the project root; fetches a canonical `DESIGN.md` (one file, exact) from getdesign.md's 70+ brand catalog.
- Or hand-author one, or paste a spec (brand guide, etc.).

make-ppt is **source-agnostic** — it only needs a `DESIGN.md` to exist; it does not care how it got there. The CLI is just a convenient, exact fetcher, not a dependency make-ppt relies on.

## Fonts

A `DESIGN.md` already names its typefaces in the typography section — resolve those to loadable web fonts (Google Fonts / Fontshare) at generation time. Keep the design's **role split** (e.g. display / body / mono); if the real fonts are licensed, use open-source substitutes — the split matters more than an exact match.

A separate `fonts.md` is **optional** — use it only to pin chosen substitutes + the exact `<link>` for a design you reuse often.

## content .md — what's on the slides

Optional. Holds the deck's content so the whole deck is `.md`-specified.

```
---
design: <designs/ folder name — omit if using a root DESIGN.md>
title: <deck title>
---

# Slide title
<!-- layout: title | content | ... -->

(markdown body)

---
(next slide)
```

- `---` separates slides · the first `#` is the slide title · `<!-- layout: ... -->` hints the slide type · the rest is plain markdown.
- No content `.md`? Gather content conversationally in Phase 1 as usual — and optionally write it back to a `<deck>.md` so the deck becomes reproducible.

## DESIGN.md → deck CSS (Phase 3)

When generating on the `.md`-driven path:

1. **Tokens → `:root`.** Every colour / spacing / radius the DESIGN.md names becomes a CSS variable. Never inline a hex the design gives a token for.
2. **Type → font stacks + utility classes.** Resolve each typeface to a loadable web font, map to a `--font-*` variable. Honour weights, letter-spacing, and uppercase/case rules exactly.
3. **Components → CSS.** Build buttons, cards, inputs, etc. per the DESIGN.md component specs.
4. **Do's / Don'ts are hard constraints.** "No bold", "no gradients", "0px radius except buttons" are not suggestions — violating one fails the deck.
5. **Viewport fitting still wins.** Wrap the design's fixed px values in `clamp()`; every slide still fits 100vh with no scroll. The design system never overrides make-ppt's non-negotiables.
6. **Single HTML.** The deck inlines everything; the `DESIGN.md` is a source spec, not a runtime dependency.

The result: a deck whose every visual choice traces to one `DESIGN.md` line — repeatable, inspectable, consistent across decks that share a design.

## Quality bar

A `.md`-driven deck is done only when it:

- [ ] renders the `DESIGN.md` faithfully — every token, every Do/Don't honoured
- [ ] fits every slide in exactly 100vh, no scroll (checked at 1280×720)
- [ ] loads the fonts the DESIGN.md names
- [ ] is a single self-contained HTML file
