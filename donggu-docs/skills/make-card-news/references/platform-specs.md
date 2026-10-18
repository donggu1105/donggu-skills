# Platform specs for card sets

Checked against official help/API pages in the 2026-09-25 deep research; re-check the live page before building any automated upload.

## LinkedIn

- Document post: PDF, PPT, PPTX, DOC, DOCX; ≤ 100 MB; ≤ 300 pages. Viewers swipe pages inline — this is the native "carousel" on LinkedIn.
- After posting, the caption can be edited but the attached document cannot → finish QA before upload.
- A multi-image post is a different format from a document post; pick one deliberately (document post for a card set).
- Carousel *ads* have their own specs; don't apply them to organic posts.

## Instagram

- App / web carousel: up to 20 photos or videos; photo ratio 1.91:1 – 3:4; max width 1080 px.
- Content Publishing API: carousel max 10 items; images JPEG ≤ 8 MB; ratio 4:5 – 1.91:1. The manual 20-item / 3:4 allowance does not carry over to automation.
- Some schedulers advertise 3:4 for auto-posting; treat that as tool-specific until tested on the actual account.
- Hence 1080×1350 (4:5) as the one working size that satisfies manual and API paths on both platforms.

## Threads

- Image posts accept up to 20 images in the app; text ≤ 500 chars, body URLs are rejected by the publishing adapter in this repo — keep links on the closing card as plain text and in the caption field the adapter allows.

## Safe areas (template defaults)

- Side margins ~7.8 %; the footer sits on the 90 % line and nothing important goes below it (platform UI overlays the bottom strip).
- Thumbnail test: the first card should read at ~300 px wide — title ≤ 3 lines, one idea.
