---
name: publish-sns
description: Use when the user asks to publish, post, or delete finalized SNS content (올려줘, 발행해줘, 게시해줘, 삭제해줘, 내려줘) on tistory, maily, threads, linkedin, or instagram, including finalized local image files.
---

# Publish SNS

## Overview

Publish channel notes from the Obsidian vault to live SNS channels through n8n webhooks, record results in the Supabase `published_posts` ledger, and handle deletion. Channels: **tistory · maily · threads · linkedin · instagram** (X is suspended — API paywall; tell the user it's on hold if asked).

**Three iron rules:**
1. **Never publish or delete without an explicit user approval AFTER showing a preview.** Channel agreement is not approval. Body shown ≠ body changed later — re-preview after any edit.
2. **The ledger is the only memory.** post_id/url live in `published_posts`, never in conversation memory.
3. **Blog/Tistory needs a section image plan, not merely “an image.”** Every Blog publish or update must include a hero image as `cover_image` **and section-specific body images distributed through the article**. Give every major `##` section a matching image; two short adjacent sections may share one only when they express the same visual concept. For a post with 3 or more `##` sections, require at least 3 images total (hero + at least 2 body images) and never leave more than 2 consecutive `##` sections without an image. Place each body image after the opening paragraph of the section it illustrates, not as a gallery at the top or bottom. Prefer the user’s real screenshots/assets; otherwise generate with `get-ai-image` when appropriate. A factual depiction of a real person, place, customer, product state, or event requires a supplied or verified asset and must never be fabricated with AI. The first image remains the hero/cover so body, list thumbnail, and OG image stay aligned. A hero plus a final related-video thumbnail does **not** satisfy this gate.

Content *formats* are NOT defined here. Text drafts are owned by `writing-social-content`; this skill accepts only finalized text and finalized image files and owns the upload and publishing contract. It does not generate cards or finished Shorts/video files.

### Post-publication review boundary

성공한 실발행 결과가 `published_posts`에 저장되면 existing DB trigger가 **발행 완료 이벤트**를 생성한다. 이 이벤트가 후속 검토의 유일한 경계다. `publish-sns`는 CORE/Snippet/MOC를 직접 생성하거나 후보를 적용하지 않는다. webhook 실패, 장부 저장 실패, preview, `dry-run`은 발행 완료 이벤트를 만들지 않는다.

## Flow

```
"<topic> <channel>에 올려줘"
  1. Find note(s):  Personal Branding/40_Channel_Packs/<folder>/<채널> - <topic>.md
     folder→channel: Blog→tistory · Maily→maily · Threads→threads · LinkedIn→linkedin · Instagram→instagram
     │
     ├─ note MISSING ──► DO NOT stop and ask for a filename.
     │     Offer to CREATE a missing text-channel draft with writing-social-content,
     │     then save the note
     │     (`status: draft`), then continue at step 2 with the new note.
     │
     └─ note EXISTS ──► 2. Extract body per channel (see table). For LinkedIn/Threads only,
                           stop the canonical body at the next level-2 heading.
                           NEVER take "everything after frontmatter"; strategy/notes/checklist
                           sections must not leak into a post.
  3. PREVIEW + APPROVAL GATE (mandatory): show title + body (or structure + first paragraphs
     + char count). Prefer `clarify` single-select buttons only when the host can return the
     selection before the native receipt expires and the Discord application does **not** route
     interactions to a separate HTTP endpoint. In the current Camille deployment, the same
     Discord application has an n8n Interactions Endpoint URL, so generic Hermes `clarify`
     components are diverted away from the gateway and fail with "application did not respond".
     Use exact later-turn text approval or the purpose-built `pub1` publishing buttons here;
     do not present generic `clarify` buttons. Put selectable labels only in `choices`, never in
     the question text. **Do not open a 15-minute native receipt and then block on a 60-minute
     button wait.** If the button transport cannot satisfy the receipt TTL, explain the
     limitation once and use exact later-turn text approval instead; never loop by silently
     minting replacement receipts. Proceed ONLY on an explicit later-turn approval whose verb
     matches the receipt operation: publish=`발행해`/`올려줘`, update=`블로그 업데이트 적용해줘`,
     delete=`삭제해줘`. A generic `승인합니다` or a cross-operation verb never authorizes mutation.
     The approval verb must be a completed affirmative imperative at the end of the message.
     Questions, deliberation,
     deferral, and negation such as `발행해 볼까?`, `나중에 발행해`, or `발행해 두지 마`
     are never approvals.
     State whether the post will include images. Threads may publish text-only only after explicit confirmation.
     Instagram requires a finalized caption. If 1–10 finalized image files are absent, STOP;
     obtain user-provided assets first or `get-ai-image` when appropriate, then rebuild and re-preview.
     Instagram must never publish text-only. Never silently drop images a showcase/proof post needs.
     maily = irreversible email send → confirm once more right before firing.
     After the final Maily click, treat only a same-origin public `/slug/posts/<id>` page whose
     visible `og:title`/`h1` matches the payload title, or an exact visible completion marker on
     a safe same-origin page, as success. Login/error/arbitrary redirects remain reconciliation.
  4. Use the native adapter (required): call `donggu_publishing_preview`, show its exact
     preview, wait for approval in a later user turn, call `donggu_publishing_approve`, then
     call `donggu_publishing_dispatch`. Maily real-send requires another later user turn and
     `donggu_publishing_confirm_maily` before dispatch. **Mutations run only through Hermes,**
     whose host-provided session/turn IDs and the actual latest persisted `SessionDB` user message enforce those
     later turns. The adapter examines only that latest user row: blank text, structured/non-string
     content, or an invalid message ID fails closed and must never fall back to an older approval.
     It re-reads that exact latest row under a `SessionDB` write transaction and executes the
     durable receipt+authorization claim before releasing the transcript writer lock; a changed
     message ID or text blocks the claim before mutation, and a later user row linearizes only
     after the authorization claim.
     Each persisted approval/confirmation row is consumed by one receipt only through a durable private filesystem claim shared across runtime instances; a single `승인` or final-confirmation message never authorizes multiple receipts, even across concurrent workers or process-local runtime objects. The approval/confirmation tools take only `receipt_id`; never synthesize an
     approval string. Claude Code may create and show a stateless preview, but Hermes must
     create a new native preview before receipt status, approval, confirmation, or dispatch;
     direct webhook, ledger, or CLI mutation is forbidden.
  5. The adapter checks `published_posts` immediately before a real publish and blocks when an
     active post or a legacy unresolved reconciliation row already exists. It then POSTs the fixed
     channel webhook and records **verified real publishes only** in `published_posts`.
     **`dry_run=true` 성공 응답은 절대 `published_posts`에 INSERT하지 않는다.** It ends as
     `completed_draft` and therefore never creates the DB-triggered publication-complete event.
     `reconciliation_required` means the external mutation occurred or may have occurred, but
     public read-back or ledger completion is incomplete. This state and any
     URL/post_id/worker `job_id`/error are
     preserved on the signed receipt only; it must not create a `published_posts` row or
     `content.published` event. Never mint a replacement publish receipt or retry automatically.
     For browser publishers, set the irreversible-mutation boundary immediately before the final
     save/publish/update/delete click. Any click, wait, read-back, browser/context close, or outer
     Playwright-manager exception after that boundary must preserve `external_mutation_possible`
     and end in reconciliation, never an ordinary retryable failure. An outer queue worker that
     cannot prove the phase must classify an unhandled publisher exception conservatively as
     uncertain; irreversible worker jobs must disable automatic retries. The receiver must atomically
     create an expiry-free terminal idempotency binding, canonical queue job bytes, and queue
     membership in one Redis operation; the binding must persist through AOF plus a data volume.
     Same-key replay may reuse only a still-durable job/result, otherwise reconciliation is required
     and re-enqueue is forbidden, including after the expiring job/result keys disappear. For n8n
     v2, a version-fixed workflow header cutover
     must run `updateNode` followed by `activateWorkflow`; rollback must republish the restored node
     the same way. A draft-only patch is not a deployed contract.
     Tistory update installs a blocking browser route before the final click and permits exactly
     one HTTPS `POST /manage/post.json` whose payload ID equals the approved post; mismatches are
     aborted before network transmission. The production adapter release must bind one exact
     blog/post capability in code (currently `donggu1105/306`); never widen it through environment
     configuration. A different ledger target requires a separately reviewed release.
     Public read-back compares an ordered semantic body event
     stream (text boundaries, block structure, links including query/fragment, duplicate image
     placements), serves the preflight-validated pinned image bytes through the browser route
     without browser DNS/network lookup, aborts unapproved same-host image requests, requires
     successful browser decode/load, and materializes the cover upload from those same strict
     preflight bytes without a second GET before binding the requested cover.
     Inspect the existing post first and resolve it through the ledger/update path.
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
- Remote image URLs must stay on the channel allowlist and resolve only to public **unicast**
  addresses. Reject literal or DNS-resolved private, loopback, link-local, unspecified, reserved,
  multicast, and known IPv4-embedded IPv6 transition forms (including IPv4-mapped, NAT64,
  6to4, and Teredo) before any network fetch; re-check every redirect.
- If the adapter is unavailable or its credentials/origin validation fails, **fail closed**.
  Direct webhook and direct ledger mutation are forbidden. The references below are diagnostic
  contract documentation only, not a fallback execution path.

### Channel extraction

| Channel | Body source in note | Payload notes | Format canon |
|---|---|---|---|
| tistory | first line = title, markdown body as-is — **but run blog-image prep first** (see below) | `category`? (default 프로덕트 엔지니어), **required public `tags` 4–7** | vault `TEMPLATE - Blog 발행 틀` |
| maily | `## 발행`: line1=title, **line2=subtitle (required)**, blank, body md as-is — **blog-image prep first if it has `![[embeds]]`** | `tags` array; `"dry_run": true` = draft only (no email) | **writing-social-content** |
| threads | `## 발행` text until the next `##` = `content`; `![[image]]` embeds → `image_urls` | ≤500 chars, 0 hashtags, 0 body URLs; native preview rejects overlength, hashtags, and unambiguous URL strings | **writing-social-content** |
| linkedin | `## Draft` final version until the next `##` | `content` only, 0 body URLs; native preview rejects unambiguous URL strings | writing-social-content |
| instagram | finalized caption + finalized local image files → `upload_images.py` → `image_urls` | 1 img=single, 2–10=carousel | finalized caption and images |

### Tags (tistory blog)

Tags are part of the approved public payload, not optional decoration.

1. Build **4–7 unique public tags** (platform hard limit 10; runtime fails below 3 or above 10).
2. Use a balanced set: one role/domain tag, 2–4 core topic tags, and 1–2 concrete problem or search-intent tags. Example for an FDE customer-interview article: `FDE`, `고객인터뷰`, `현장관찰`, `도메인지식`, `요구사항정의`, `업무분석`.
3. Source candidates from semantic `topics` and `주제/*` frontmatter entries. Strip the `주제/` prefix. Never publish operational/private namespaces such as `채널/*`, `브랜드/*`, project tags, or any tag containing `/`.
4. Trim whitespace and leading `#`, deduplicate case-insensitively, keep each tag at 1–30 characters, and show the **exact final list** in the native preview.
5. After editor input, poll the Tistory tag chips for a bounded time and compare them with the requested set before clicking publish. After publication, compare only the post tag container (`dl.list_tag`) again. Missing/extra tags before publish are a hard failure. Missing URL, public DOM/read-back failure, or tag mismatch after submit is reconciliation-required—even for image-only bodies—and must never trigger blind reposting.
6. Tistory may normalize acronym display casing (`FDE` → `Fde`). Compare case-insensitively and report the platform-normalized display rather than repeatedly rewriting the post.

### Images (blog: tistory · maily — inline body images)

Blog bodies carry images as Obsidian wikilink embeds (`![[geudwi-hero.jpg]]`) — vault-local refs that **break when sent to tistory/maily as-is** (the webhook ships the markdown verbatim; the reader can't see vault files). So **before** building the tistory/maily payload, convert them:

```
python3 <skill>/prepare_blog_images.py "<note.md>" --out /tmp/<slug>.pub.md
#   ![[local.jpg]] 추출 → sns-media 버킷에 upsert 업로드 → ![](공개URL) 치환
#   → /tmp/<slug>.pub.md 가 발행용 본문. 키는 n8n .env 자동 로드.
#   → /tmp/<slug>.pub.md.cover 에 hero(첫 이미지) URL = 대표이미지 소스.
```

Then extract title (first line) + body **from the converted file** and send that as `content` to `sns-pub-tistory` / `sns-pub-maily`. The script is idempotent (upsert) — re-running reuses the same URLs. Storage path: `sns-media/blog/<YYYY>/<MM-DD>/<slug>/<file>` (public). If it exits non-zero (`unresolved` image), STOP — a wikilink points at a file not in the vault; fix the embed before publishing, never ship a broken `![[...]]`.

**Mandatory tistory image gate:** before native preview, count the `##` sections and build an explicit image-slot plan. Generate/source missing images, insert each one after the matching section’s opening paragraph, then run conversion. Verify (a) `/tmp/<slug>.pub.md.cover` exists and is non-empty, (b) every image URL is publicly reachable, (c) the converted body satisfies the section-coverage rule above, (d) the images are visually distinct and actually match their assigned section, and (e) the hero is passed as `cover_image`. Report the total image count and section placements in the preview. If any check fails, STOP. The runtime counts inline Markdown images and reports their H2 placements, but independently verify the converted Markdown as the source of truth. Outside renderer-recognized fenced code, only inline Markdown image syntax is allowed; raw HTML tags and reference-style images are fail-closed. The fence exception is deliberately the safe subset of Python-Markdown `fenced_code`: column-zero backtick/tilde markers, an optional single language token, and an exact same-length closing marker. Indented pseudo-fences, free-form info strings, tabs/form-feeds, unequal markers, and unclosed fences never suppress raw-resource validation.

Public image URLs must also reject browser-parser ambiguity before probing: literal/encoded
backslashes, literal/percent-encoded dot segments, and control/whitespace characters are invalid.
The editor route must abort both the exact approved URL and every image request to an approved
hostname so Chromium normalization or DNS rebinding cannot turn an approved probe into a second
browser lookup.

**tistory 대표이미지(썸네일/OG)**: tistory는 본문의 외부 `<img>` 핫링크로는 대표이미지를 못 잡는다 — 발행기가 **별도로 hero를 티스토리에 업로드**해야 og:image가 잡힌다. `sns-pub-tistory`/`sns-update-tistory` 호출 시 `cover_image`(= `.cover` 파일의 hero URL)를 같이 보내면 발행기가 발행모달의 '대표이미지 추가'에 업로드한다. 빠뜨리면 본문 이미지는 보여도 썸네일/공유 카드가 비는 placeholder가 된다. (maily는 cover 개념 없음 — 보내지 말 것.)

### Images (threads · instagram — finalized files)

- **Threads text-only gate**: Threads may publish text-only only after explicit confirmation. If images are wanted, use finalized local files referenced by `## 발행` `![[embeds]]`; obtain user-provided assets first or `get-ai-image` when appropriate before rebuilding the preview.
- **Ordered upload**: run `python3 <skill>/upload_images.py <channel> <topic-slug> <bucket> file1 ...`. The input file order is preserved in the returned `image_urls`. The script reads credentials from the environment and does not place expanded service keys in argv.
- **Instagram no-images gate — STOP**: If 1–10 finalized image files are absent, STOP; obtain user-provided assets first or `get-ai-image` when appropriate, then rebuild and re-preview. Instagram must never publish text-only. Require a finalized caption as well. Factual real-world imagery requires a supplied or verified asset. This skill uploads and publishes finalized files; it does not create a card deck or video.

## Webhook reference

Diagnostic contract only. The runtime owns these endpoints, headers, redirects, and ledger writes;
agents must never call mutation webhooks directly. All require `X-SNS-Token`; never print token values.

| Purpose | POST `https://n8n.donggu.site/webhook/…` | Body | Response |
|---|---|---|---|
| tistory pub | `sns-pub-tistory` | `{title, content, tags, category?, cover_image?}` | `{success, url, post_id, error}` |
| tistory **update** | `sns-update-tistory` | `{post_id, title, content, tags, category?, cover_image?, dry_run?}` | `{success, url, post_id, error}` |
| maily pub | `sns-pub-maily` | `{title, content, subtitle?, tags?, dry_run?}` | `{success, url, error}` (no post_id) |
| threads pub | `sns-pub-threads` | `{content, image_urls?}` | `{success, url, post_id, error}` |
| linkedin pub | `sns-pub-linkedin` | `{content}` | `{success, url, post_id, error}` |
| instagram pub | `sns-pub-instagram` | `{image_urls, caption}` | `{success, url, post_id, error}` |
| delete | `sns-del-tistory` / `sns-del-threads` | `{post_id}` | `{success, error}` |

Delete exists only for tistory·threads. maily emails can't be recalled; linkedin = manual delete.

**tistory edit-in-place**: the adapter resolves `post_id` from the ledger and calls `sns-update-tistory` — **same URL preserved**, no delete+repost. The known ledger post ID is authoritative throughout submit and read-back; never infer an update target from a redirect or the latest-post list. Use it to backfill/fix a published post: run `prepare_blog_images.py`, then use adapter preview → approve → dispatch. Never SELECT a post ID and POST manually.

**tistory `session_expired` recovery**: treat this as a confirmed pre-publication failure only after the dispatch result reports `success:false, error:"session_expired"`. Before any retry, verify that there is no returned URL/post ID, no active ledger row for the topic, and no successful tistory execution. Run `api/scripts/recapture_tistory.py` inside the `api-worker` container, ask the user to approve the Kakao 2FA push, and require both persistent Kakao cookies and `manage/posts` reachability. Then create a fresh native preview from the exact same payload, obtain a new later-turn explicit approval, and dispatch once. Never blindly replay the failed receipt or turn direct FastAPI/n8n mutation calls into the routine path.

## Ledger (Supabase `fvfayignxybdyyravorg` · table `published_posts`)

The adapter alone owns ledger SELECT/INSERT/PATCH. It requires exactly one returned row for writes.
Delete flow: adapter preview resolves the latest active ledger row → show topic + URL → later-turn approve → dispatch → exact active-row `deleted_at` PATCH. Not in ledger, zero-row write, or multi-row write → refuse/reconciliation; never guess or issue manual SQL.

## Red Flags — STOP

- About to POST a pub webhook without having shown a preview *and* received explicit approval in this conversation → STOP, preview first. "The note already says status:draft and user said 올려줘 by topic" is NOT approval of the body.
- Extracted body = whole note after frontmatter → STOP, use the channel's section (`## 발행` / `## Draft`).
- Threads body is over 500자를 넘거나 해시태그·본문 URL을 포함함, or LinkedIn body contains a URL → STOP before preview; remove the URL from the canonical body, save the corrected draft, and re-preview.
- No text-channel note found and you're about to ask the user for a filename → STOP, offer to create the draft via `writing-social-content` instead. For missing images, use supplied assets first or `get-ai-image` when appropriate.
- post_id from conversation memory → STOP, SELECT from the ledger.
- maily without a subtitle line, or real-send without the second confirmation → STOP.
- About to send a Threads post text-only without explicit confirmation → STOP, confirm that no images are intended.
- About to send an Instagram post without 1–10 finalized `image_urls` → STOP, obtain finalized images, then rebuild and re-preview.
- About to POST tistory/maily content that still contains `![[…]]` wikilinks → STOP, you skipped `prepare_blog_images.py`; the images will break in the published post.
- Tistory preview has no exact tag list, fewer than 4 public tags, more than 7 without a stated reason, duplicate tags, or any namespaced tag containing `/` → STOP and rebuild the public tag set.

| Excuse | Reality |
|---|---|
| "User said 올려줘, that IS the approval" | They approved the *intent*, not the *body*. Preview, then approval. |
| "Note doesn't exist, user must tell me where it is" | For a text channel, offer the `writing-social-content` path. For imagery, ask for supplied assets or use `get-ai-image` when appropriate. |
| "I remember the post_id from earlier" | Sessions die. The ledger doesn't. |
| "User said 올려/다시 올려, so text-only is fine" | For Threads, explicitly confirm text-only. Instagram never publishes text-only. |
| "Body has `![[…]]`, tistory will render it" | It won't. Vault wikilinks are local. Run `prepare_blog_images.py` → `![](url)` first. |
