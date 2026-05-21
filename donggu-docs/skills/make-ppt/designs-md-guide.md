# designs-md-guide — the .md-driven path

How make-ppt turns a project's `designs/` library into a deck. The `.md` files are the **standard**: `DESIGN.md` decides the look, a content `.md` decides what's on the slides, and make-ppt synthesizes them into a single self-contained HTML deck.

This path is **additive** — it does not change frontend-slides' mood/preview discovery. Use it when a design system already exists or the user wants a specific brand/aesthetic.

## The designs/ folder

A project keeps its design systems in `./designs/`. One design = one subfolder.

```
designs/
  README.md            (선택) 라이브러리 안내
  <name>/
    DESIGN.md           필수 — 디자인 시스템 스펙
    fonts.md            필수 — 폰트 매핑 + 웹폰트 <link>
    <deck>.md           덱 콘텐츠 (덱마다 하나, 여러 개 가능)
    <deck>.html         생성된 덱 (단일 HTML)
```

If a project has no `designs/` yet, make-ppt can create one: author a `DESIGN.md`, add a `fonts.md`, done.

The generated deck (`<deck>.html`) is written next to its content `.md` inside `designs/<name>/` by default — unless the project keeps decks elsewhere, in which case follow that convention.

## DESIGN.md — the look

A `DESIGN.md` is a prose + table spec of a design system: colours (hex), typography (family, size, weight, letter-spacing), spacing scale, border radius, components, and **Do's / Don'ts**. It is the same kind of artifact as a `STYLE_PRESETS.md` preset — just richer, and per-project.

It does not need a fixed schema. It must be specific enough that every colour, font, and rule can be read straight off it. Sites like getdesign.md publish ready-made `DESIGN.md` files for real brands; brand guides and hand-written specs work equally well.

## fonts.md — the fonts

Maps the design's typefaces to loadable web fonts (Google Fonts / Fontshare) and gives the `<link>` to drop into the deck `<head>`. If the real fonts are licensed or unavailable, it documents open-source substitutes — keeping the **role split** the design defines (e.g. display / body / mono) matters more than an exact typeface match.

## content .md — what's on the slides

Optional. Holds the deck's content so the whole deck is `.md`-specified.

```
---
design: <designs/ 폴더 이름>
title: <덱 제목>
---

# 슬라이드 제목
<!-- layout: title | content | ... -->

(마크다운 본문)

---
(다음 슬라이드)
```

- `---` separates slides · the first `#` is the slide title · `<!-- layout: ... -->` hints the slide type · the rest is plain markdown.
- No content `.md`? Gather content conversationally in Phase 1 as usual — and optionally write it back to a `<deck>.md` so the deck becomes reproducible.

## DESIGN.md → deck CSS (Phase 3)

When generating on the `.md`-driven path:

1. **Tokens → `:root`.** Every colour / spacing / radius the DESIGN.md names becomes a CSS variable. Never inline a hex the design gives a token for.
2. **Type → font stacks + utility classes.** Map each typeface (via `fonts.md`) to a `--font-*` variable. Honour weights, letter-spacing, and uppercase/case rules exactly.
3. **Components → CSS.** Build buttons, cards, inputs, etc. per the DESIGN.md component specs.
4. **Do's / Don'ts are hard constraints.** "No bold", "no gradients", "0px radius except buttons" are not suggestions — violating one fails the deck.
5. **Viewport fitting still wins.** Wrap the design's fixed px values in `clamp()`; every slide still fits 100vh with no scroll. The design system never overrides make-ppt's non-negotiables.
6. **Single HTML.** The deck inlines everything; `designs/` is a source library, not a runtime dependency.

The result: a deck whose every visual choice traces to one `DESIGN.md` line — repeatable, inspectable, consistent across decks that share a design.

## Quality bar

A `.md`-driven deck is done only when it:

- [ ] renders the `DESIGN.md` faithfully — every token, every Do/Don't honoured
- [ ] fits every slide in exactly 100vh, no scroll (checked at 1280×720)
- [ ] loads the fonts named in `fonts.md`
- [ ] is a single self-contained HTML file
