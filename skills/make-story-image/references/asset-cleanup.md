# Asset cleanup for story heroes

Product renders used as story heroes often ship with a stage: a plinth, floor plane or reflection tray with a straight
edge. On a 9:16 canvas that edge lands right where the copy starts and reads as a seam. Layout fades can't hide a
straight edge — fix the asset once and save it as `<name>-story.jpg` next to the spec.

## Procedure (Pillow, stdlib-only script inline with `terminal`)

1. **Measure the stage.** Row-mean luminance down the image; the plinth shows as a plateau (e.g. rows 56–65 % of
   height at lum ≈ 18–34 on a ≈ 5 background). A `vision_analyze` pass confirms whether it is a hard strip or a soft
   reflection — only hard strips need this procedure.
2. **Sample the true background beside the object**, not at the top of the frame (a render's top rows are often a
   different dark: FDE톤 capsule top = (6,11,14), beside the object = (4,9,12); the difference is a visible step).
3. **Mask the object geometrically.** For a capsule/pill: object pixels = colour distance from background > 50 within
   the object's rows (exclude the plinth rows); PCA on those pixels gives the axis; take the axis extremes as the two
   end points and the 99.5-percentile half-width as the radius; then grid-search radius (+0…+12 px) and lateral offset
   (±12 px) minimising `outside_pixels × 4 + (mask_area − object_pixels)`. For a round object use an ellipse the same way.
   Blur the mask 1 px. **Do not use a colour-difference mask as the final matte** — it drops the darkest chrome edge
   pixels and leaves a dark fringe between the object and its glow.
4. **Fill the whole canvas** with the sampled background colour, draw a **radial glow centred on the object's
   lit end** (concentric ellipses, alpha ∝ (1 − r/R)²; R ≈ 0.45 × width; Gaussian blur ≈ 40), then composite the
   object on top with the mask. The glow must bleed above the object as well as below — a one-sided pool under a
   straight edge reads as a floor again.
5. **Reposition on canvas, don't crop.** Paste the cleaned asset onto a same-size background shifted right/down so
   the handle pill (top-left) and the copy block stay clear of the object (FDE톤 capsule: +170 px right; knot:
   +110 px down for headroom under the progress bar).
6. **Verify** with `vision_analyze` on the asset alone ("any hard line, rectangle, fringe, cut edge?") and again on
   the rendered frame. Ship only on an explicit no-blockers answer.

Worked example: `~/workspace/hermes/annie/2026-10-27-fdethon-cardnews/story/` (capsule-story.jpg, knot-story.jpg) —
five attempts, the geometric mask was the one that passed.
