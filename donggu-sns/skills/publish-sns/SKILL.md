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

### Post-publication review boundary

성공한 실발행 결과가 `published_posts`에 저장되면 existing DB trigger가 **발행 완료 이벤트**를 생성한다. 이 이벤트가 후속 검토의 유일한 경계다. `publish-sns`는 CORE/Snippet/MOC를 직접 생성하거나 후보를 적용하지 않는다. webhook 실패, 장부 저장 실패, preview, `dry-run`은 발행 완료 이벤트를 만들지 않는다.

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
  4. Use the native adapter (required): call `donggu_publishing_preview`, show its exact
     preview, wait for approval in a later user turn, call `donggu_publishing_approve`, then
     call `donggu_publishing_dispatch`. Maily real-send requires another later user turn and
     `donggu_publishing_confirm_maily` before dispatch. **Mutations run only through Hermes,**
     whose host-provided session/turn IDs and the actual latest persisted `SessionDB` user message enforce those
     later turns. Each persisted approval/confirmation row is consumed by one receipt only; a single `승인` or final-confirmation message never authorizes multiple receipts. The approval/confirmation tools take only `receipt_id`; never synthesize an
     approval string. Claude Code may create and show a stateless preview, but Hermes must
     create a new native preview before receipt status, approval, confirmation, or dispatch;
     direct webhook, ledger, or CLI mutation is forbidden.
  5. The adapter POSTs the fixed channel webhook and records **real-publish successes only**
     in `published_posts`. **`dry_run=true` 성공 응답은 절대 `published_posts`에 INSERT하지 않는다.**
     It ends as `completed_draft` and therefore never creates the DB-triggered
     publication-complete event.
     `reconciliation_required` means the external mutation succeeded but the ledger did not;
     never retry publication automatically. Reconcile the returned URL/post_id first.
  6. Report per-channel success/failure + URLs. Update note frontmatter `status: published`
     only when at least one real publish succeeded and its ledger write completed. A dry-run-only
     result leaves the note status unchanged.
```

### Native adapter contract

The Claude and Hermes packages share one validation/runtime core, but only Hermes supplies
trusted user-turn metadata. Do not reimplement webhook routing or ledger writes in
harness-specific scripts.

- Hermes tools: `donggu_publishing_preview` → later-turn `donggu_publishing_approve` →
  Maily real-send only: later-turn `donggu_publishing_confirm_maily` →
  `donggu_publishing_dispatch`; inspect uncertainty with
  `donggu_publishing_receipt_status`.
- Claude bridge: pipe one bounded JSON request to
  `python3 <donggu-sns-package-root>/runtime/publishing_cli.py`. Only stateless `preview` is
  accepted. `status`, `approve`, `confirm_maily`, and `dispatch` fail closed because Claude does
  not provide the trusted in-process Hermes runtime or host turn IDs.
- Dispatch receipts expire after 15 minutes and are one-shot. The HMAC key exists only in the
  Hermes gateway process; a gateway restart invalidates unfinished receipts, so re-preview.
  A failed, uncertain, or reconciliation-required receipt must not be replayed.
- If the adapter is unavailable or its credentials/origin validation fails, **fail closed**.
  Direct webhook and direct ledger mutation are forbidden. The references below are diagnostic
  contract documentation only, not a fallback execution path.

### Channel extraction (format canon = make-* skill)

| Channel | Body source in note | Payload notes | Format canon |
|---|---|---|---|
| tistory | first line = title, markdown body as-is — **but run blog-image prep first** (see below) | `category`? (default 프로덕트 엔지니어), `tags` array | vault `TEMPLATE - Blog 발행 틀` |
| maily | `## 발행`: line1=title, **line2=subtitle (required)**, blank, body md as-is — **blog-image prep first if it has `![[embeds]]`** | `tags` array; `"dry_run": true` = draft only (no email) | **writing-social-content** |
| threads | `## 발행` text = `content` verbatim; `![[image]]` embeds → `image_urls` in order | ≤500 chars (warn if over), 1 hashtag max | **writing-social-content** |
| linkedin | `## Draft` final version | `content` only | writing-social-content |
| instagram | card texts in note → self-contained HTML → render webhook → `image_urls` + `caption` | 1 img=single, 2–10=carousel | **make-insta-card-news** (Mode B) |

### Images (blog: tistory · maily — inline body images)

Blog bodies carry images as Obsidian wikilink embeds (`![[geudwi-hero.jpg]]`) — vault-local refs that **break when sent to tistory/maily as-is** (the webhook ships the markdown verbatim; the reader can't see vault files). So **before** building the tistory/maily payload, convert them:

```
python3 <skill>/prepare_blog_images.py "<note.md>" --out /tmp/<slug>.pub.md
#   ![[local.jpg]] 추출 → sns-media 버킷에 upsert 업로드 → ![](공개URL) 치환
#   → /tmp/<slug>.pub.md 가 발행용 본문. 키는 n8n .env 자동 로드.
#   → /tmp/<slug>.pub.md.cover 에 hero(첫 이미지) URL = 대표이미지 소스.
```

Then extract title (first line) + body **from the converted file** and send that as `content` to `sns-pub-tistory` / `sns-pub-maily`. The script is idempotent (upsert) — re-running reuses the same URLs. Storage path: `sns-media/blog/<YYYY>/<MM-DD>/<slug>/<file>` (public). If it exits non-zero (`unresolved` image), STOP — a wikilink points at a file not in the vault; fix the embed before publishing, never ship a broken `![[...]]`.

**tistory 대표이미지(썸네일/OG)**: tistory는 본문의 외부 `<img>` 핫링크로는 대표이미지를 못 잡는다 — 발행기가 **별도로 hero를 티스토리에 업로드**해야 og:image가 잡힌다. `sns-pub-tistory`/`sns-update-tistory` 호출 시 `cover_image`(= `.cover` 파일의 hero URL)를 같이 보내면 발행기가 발행모달의 '대표이미지 추가'에 업로드한다. 빠뜨리면 본문 이미지는 보여도 썸네일/공유 카드가 비는 placeholder가 된다. (maily는 cover 개념 없음 — 보내지 말 것.)

### Images (threads · instagram — unified pipeline)

- **Image gate (ask first)**: threads/instagram images come only from `## 발행` `![[embeds]]`. No embeds → text-only. Before posting, confirm with the user whether images are wanted; if yes and the note has none, get them (user screenshot or a fresh render) BEFORE firing — never post text-only and backfill later.
- **New cards**: build self-contained HTML (absolute URLs only — `make-insta-card-news` Mode B) → POST render webhook (`sns-render-instagram` / `sns-render-threads`, body `{html, slug}`) → api renders 4:5 + uploads to `sns-cards/<channel>/<YYYY>/<MM-DD>/<slug>-<HHMMSS>/<NN>.png` → returns `image_urls` in carousel order.
- **User-provided screenshots**: use `make-insta-card-news/supabase_upload.py`, which reads credentials from the environment and does not place expanded service keys in argv. Upload to the same dated path; 409 means reuse the existing public URL.

## Webhook reference

Diagnostic contract only. The runtime owns these endpoints, headers, redirects, and ledger writes;
agents must never call mutation webhooks directly. All require `X-SNS-Token`; never print token values.

| Purpose | POST `https://n8n.donggu.site/webhook/…` | Body | Response |
|---|---|---|---|
| tistory pub | `sns-pub-tistory` | `{title, content, category?, tags?, cover_image?}` | `{success, url, post_id, error}` |
| tistory **update** | `sns-update-tistory` | `{post_id, title, content, category?, tags?, cover_image?, dry_run?}` | `{success, url, error}` |
| maily pub | `sns-pub-maily` | `{title, content, subtitle?, tags?, dry_run?}` | `{success, url, error}` (no post_id) |
| threads pub | `sns-pub-threads` | `{content, image_urls?}` | `{success, url, post_id, error}` |
| linkedin pub | `sns-pub-linkedin` | `{content}` | `{success, url, post_id, error}` |
| instagram pub | `sns-pub-instagram` | `{image_urls, caption}` | `{success, url, post_id, error}` |
| render (insta/threads) | `sns-render-instagram` / `sns-render-threads` | `{html, slug}` | `{success, image_urls, folder, count}` |
| delete | `sns-del-tistory` / `sns-del-threads` | `{post_id}` | `{success, error}` |

Delete exists only for tistory·threads. maily emails can't be recalled; linkedin = manual delete.

**tistory edit-in-place**: the adapter resolves `post_id` from the ledger and calls `sns-update-tistory` — **same URL preserved**, no delete+repost. Use it to backfill/fix a published post: run `prepare_blog_images.py`, then use adapter preview → approve → dispatch. Never SELECT a post ID and POST manually.

## Ledger (Supabase `fvfayignxybdyyravorg` · table `published_posts`)

The adapter alone owns ledger SELECT/INSERT/PATCH. It requires exactly one returned row for writes.
Delete flow: adapter preview resolves the latest active ledger row → show topic + URL → later-turn approve → dispatch → exact active-row `deleted_at` PATCH. Not in ledger, zero-row write, or multi-row write → refuse/reconciliation; never guess or issue manual SQL.

## Red Flags — STOP

- About to POST a pub webhook without having shown a preview *and* received explicit approval in this conversation → STOP, preview first. "The note already says status:draft and user said 올려줘 by topic" is NOT approval of the body.
- Extracted body = whole note after frontmatter → STOP, use the channel's section (`## 발행` / `## Draft`).
- No note found and you're about to ask the user for a filename → STOP, offer to create the draft via the matching writing-social-content / make-* skill instead.
- post_id from conversation memory → STOP, SELECT from the ledger.
- maily without a subtitle line, or real-send without the second confirmation → STOP.
- About to send a threads/instagram post text-only (no `image_urls`) when it's a showcase/proof post or its `## 발행` has no embeds → STOP, confirm images with the user first.
- About to POST tistory/maily content that still contains `![[…]]` wikilinks → STOP, you skipped `prepare_blog_images.py`; the images will break in the published post.

| Excuse | Reality |
|---|---|
| "User said 올려줘, that IS the approval" | They approved the *intent*, not the *body*. Preview, then approval. |
| "Note doesn't exist, user must tell me where it is" | Creating it is your job — offer the make-* path. |
| "I remember the post_id from earlier" | Sessions die. The ledger doesn't. |
| "User said 올려/다시 올려, so text-only is fine" | Re-posting ≠ an image decision. Confirm whether images should ride along first. |
| "Body has `![[…]]`, tistory will render it" | It won't. Vault wikilinks are local. Run `prepare_blog_images.py` → `![](url)` first. |
