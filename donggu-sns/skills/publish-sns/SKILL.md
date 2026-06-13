---
name: publish-sns
description: Use when the user asks to publish, post, or delete SNS content (올려줘, 발행해줘, 게시해줘, 삭제해줘, 내려줘) on tistory, maily, threads, linkedin, or instagram — including when no draft note exists yet, or when a make-*/writing-* skill has just produced a channel note that should go live.
---

# Publish SNS

## Overview

Publish channel notes from the Obsidian vault to live SNS channels through n8n webhooks, record results in the Supabase `published_posts` ledger, and handle deletion. Channels: **tistory · maily · threads · linkedin · instagram** (X is suspended — API paywall; tell the user it's on hold if asked).

**Two iron rules:**
1. **Never publish or delete without an explicit user approval AFTER showing a preview.** Channel agreement is not approval. Body shown ≠ body changed later — re-preview after any edit.
2. **The ledger is the only memory.** post_id/url live in `published_posts`, never in conversation memory.

Content *formats* are NOT defined here — each channel's note structure is owned by its authoring skill (text channels = `writing-social-content`, cards = `make-insta-card-news`). This skill owns the *publishing* contract only.

## Flow

```
"<topic> <channel>에 올려줘"
  1. Find note(s):  Personal Branding/50_Channel_Packs/1_SNS/<folder>/<채널> - <topic>.md
     folder→channel: Blog→tistory · Maily→maily · Threads→threads · LinkedIn→linkedin · Instagram→instagram
     │
     ├─ note MISSING ──► DO NOT stop and ask for a filename.
     │     Offer to CREATE it first: draft with the matching skill
     │     (text channels = writing-social-content, cards = make-insta-card-news,
     │      video = make-shorts), save the note
     │     (`status: draft`), then continue at step 2 with the new note.
     │
     └─ note EXISTS ──► 2. Extract body per channel (see table) — `## 발행` section is the
                           canonical body. NEVER take "everything after frontmatter";
                           strategy/notes/checklist sections must not leak into a post.
  3. PREVIEW + APPROVAL GATE (mandatory): show title + body (or structure + first paragraphs
     + char count) and ask. Proceed ONLY on an explicit "올려"-class approval.
     State whether the post will include images. For threads/instagram, if the `## 발행`
     section has no `![[image]]` embeds the post goes out TEXT-ONLY — say so and confirm
     that's intended (offer to source/render images) before firing. Never silently drop
     images a showcase/proof post needs.
     maily = irreversible email send → confirm once more right before firing.
  4. POST channel webhook(s) (reference below). Header `X-SNS-Token: $SNS_WEBHOOK_TOKEN`.
     Synchronous, 30–60s → timeout ~200s. Channels are independent — one failure doesn't
     stop the others.
  5. INSERT successes into `published_posts` (maily has no post_id → null).
  6. Report per-channel success/failure + URLs. Update note frontmatter `status: published`.
```

### Channel extraction (format canon = make-* skill)

| Channel | Body source in note | Payload notes | Format canon |
|---|---|---|---|
| tistory | first line = title, markdown body as-is | `category`? (default 프로덕트 엔지니어), `tags` array | vault `TEMPLATE - Blog 발행 틀` |
| maily | `## 발행`: line1=title, **line2=subtitle (required)**, blank, body md as-is | `tags` array; `"dry_run": true` = draft only (no email) | **writing-social-content** |
| threads | `## 발행` text = `content` verbatim; `![[image]]` embeds → `image_urls` in order | ≤500 chars (warn if over), 1 hashtag max | **writing-social-content** |
| linkedin | `## Draft` final version | `content` only | writing-social-content |
| instagram | card texts in note → self-contained HTML → render webhook → `image_urls` + `caption` | 1 img=single, 2–10=carousel | **make-insta-card-news** (Mode B) |

### Images (threads · instagram — unified pipeline)

- **Image gate (ask first)**: threads/instagram images come only from `## 발행` `![[embeds]]`. No embeds → text-only. Before posting, confirm with the user whether images are wanted; if yes and the note has none, get them (user screenshot or a fresh render) BEFORE firing — never post text-only and backfill later.
- **New cards**: build self-contained HTML (absolute URLs only — `make-insta-card-news` Mode B) → POST render webhook (`sns-render-instagram` / `sns-render-threads`, body `{html, slug}`) → api renders 4:5 + uploads to `sns-cards/<channel>/<YYYY>/<MM-DD>/<slug>-<HHMMSS>/<NN>.png` → returns `image_urls` in carousel order.
- **User-provided screenshots**: upload the vault file directly to the same dated path: `curl -X POST "https://fvfayignxybdyyravorg.supabase.co/storage/v1/object/sns-cards/<channel>/<dated-path>/<NN>.png" -H "Authorization: Bearer $SUPABASE_SERVICE_KEY" -H "Content-Type: image/png" --data-binary @<file>` (409 = already there, reuse the public URL).

## Webhook reference

Public endpoints (Cloudflare Tunnel). All require header `X-SNS-Token: $SNS_WEBHOOK_TOKEN`. Never print token values.

| Purpose | POST `https://n8n.donggu.site/webhook/…` | Body | Response |
|---|---|---|---|
| tistory pub | `sns-pub-tistory` | `{title, content, category?, tags?}` | `{success, url, post_id, error}` |
| maily pub | `sns-pub-maily` | `{title, content, subtitle?, tags?, dry_run?}` | `{success, url, error}` (no post_id) |
| threads pub | `sns-pub-threads` | `{content, image_urls?}` | `{success, url, post_id, error}` |
| linkedin pub | `sns-pub-linkedin` | `{content}` | `{success, url, post_id, error}` |
| instagram pub | `sns-pub-instagram` | `{image_urls, caption}` | `{success, url, post_id, error}` |
| render (insta/threads) | `sns-render-instagram` / `sns-render-threads` | `{html, slug}` | `{success, image_urls, folder, count}` |
| delete | `sns-del-tistory` / `sns-del-threads` | `{post_id}` | `{success, error}` |

Delete exists only for tistory·threads. maily emails can't be recalled; linkedin = manual delete.

## Ledger (Supabase `fvfayignxybdyyravorg` · table `published_posts`)

```sql
-- after each successful publish
INSERT INTO published_posts (topic, channel, note_path, post_id, url)
VALUES ('<topic>', '<channel>', '<vault path>', '<post_id|null>', '<url>');

-- find delete target (never delete what's not in the ledger)
SELECT post_id, url FROM published_posts
WHERE topic='<topic>' AND channel='<ch>' AND deleted_at IS NULL
ORDER BY published_at DESC LIMIT 1;

-- after successful delete
UPDATE published_posts SET deleted_at = now() WHERE channel='<ch>' AND post_id='<id>';
```

Delete flow: ledger SELECT → show the user *which* post (topic + url) and confirm → delete webhook → `deleted_at` UPDATE → report. Not in ledger → refuse (no guessing).

## Red Flags — STOP

- About to POST a pub webhook without having shown a preview *and* received explicit approval in this conversation → STOP, preview first. "The note already says status:draft and user said 올려줘 by topic" is NOT approval of the body.
- Extracted body = whole note after frontmatter → STOP, use the channel's section (`## 발행` / `## Draft`).
- No note found and you're about to ask the user for a filename → STOP, offer to create the draft via the matching writing-social-content / make-* skill instead.
- post_id from conversation memory → STOP, SELECT from the ledger.
- maily without a subtitle line, or real-send without the second confirmation → STOP.
- About to send a threads/instagram post text-only (no `image_urls`) when it's a showcase/proof post or its `## 발행` has no embeds → STOP, confirm images with the user first.

| Excuse | Reality |
|---|---|
| "User said 올려줘, that IS the approval" | They approved the *intent*, not the *body*. Preview, then approval. |
| "Note doesn't exist, user must tell me where it is" | Creating it is your job — offer the make-* path. |
| "I remember the post_id from earlier" | Sessions die. The ledger doesn't. |
| "User said 올려/다시 올려, so text-only is fine" | Re-posting ≠ an image decision. Confirm whether images should ride along first. |
