# NaverBlog vault handoff

## Scope and source of truth

This reference owns the publishing handoff, not writing style or the vault schema. Resolve the active vault using `obsidian`, read its `AGENTS.md` and `Personal Branding/_GUIDES/RULES.md`. Do not create a separate vault, generic wiki, or copy of shared sources.

- Notes: `Personal Branding/40_Channel_Packs/NaverBlog/NaverBlog - <제목>.md`.
- Index: `Personal Branding/40_Channel_Packs/NaverBlog/INDEX - NaverBlog.md`.
- Template: `NaverBlog/_anchors/TEMPLATE - NaverBlog 발행 틀.md`.
- `Blog/` and `channel: blog` remain Tistory. `NaverBlog/` uses `channel: naver_blog`.
- Do not select a Tistory `status: published` note as a Naver post, or relabel it as Naver. Separate notes may link through `sources` and `adapted_from`; they do not inherit approval, receipt, or publication status.

## Metadata and body boundary

Read only a `type: channel_pack`, `channel: naver_blog` note, never an index/guide/template. `status: draft` is not approval. Do not recreate the retired `approved` frontmatter status as an authorization mechanism.

1. Require exactly one top-level `# 발행 원고` followed by exactly one `# 편집 메모` boundary; ignore headings inside fenced code when locating boundaries. Missing, reversed, duplicated, or unexpected H1 boundaries fail closed.
2. First nonblank line between them is the exact title, without a heading marker. Remaining text is the content. Preserve H2/H3 paragraphs, links, and asset placements in the canonical note; never flatten or silently remove them to fit current runtime limitations.
3. Never include frontmatter, section boundary labels, edit notes, research/source inventory outside the manuscript, image plans, statistics, or private working remarks in the payload. A source citation deliberately written in the manuscript remains part of the public text.
4. Resolve blog ID from active configuration (currently `beyonddeploy`), validate it against the requested account. Do not guess an ID from note content.
5. Require the exact `category` from RULES: `FDE의 일`, `AX 현장노트`, `Beyond Deploy`, or `주간 회고`. These are category names, not Naver topic IDs; do not substitute or guess numeric IDs.
6. `topics` are internal classification. Only `public_tags` are public tag candidates. Deduplicate/trim, exclude operational namespaces and irrelevant terms, then show the exact final `tags` in preview. Never auto-copy the legacy fixed TAG_GUIDE set into Naver. No fixed count is an SEO promise; actual limits are the native schema's contract, not a platform-wide claim.

## Readiness and public approval

As of 2026-09-20, source integration is installed but activation is LOCKED. Re-check live runtime documentation/configuration at use time; this text is not a readiness probe.

- `NAVER_BLOG_ENABLED=false`, blank DOM contract until user-controlled login and live editor verification.
- Current backend rejects images, cover, and rich Markdown. A manuscript may intentionally contain these while being prepared. Unsupported content is a blocker, not permission to publish a stripped variant.
- SmartEditor platform capabilities do not imply our publisher supports them.
- Keep user login, consent to editor input/autosave, and exact later-turn public approval separate.
- Publish only through native preview → later-turn execute. Never call a direct endpoint or bypass an unavailable native channel.
- Requested images need an approved placement/cover plan and verified renderer support. Do not impose Tistory's mandatory image-count gate as a Naver search rule.

After a real publish, the public content and adapter ledger write must both be verified before changing **only this Naver note** to `status: published` and recording verified `published_at`. Dry-run, attempted submission, unavailable login, or reconciliation leaves it draft. Post IDs/URLs remain owned by `published_posts`; don't create a competing local publication ledger.

## Verification

- Confirm the chosen note is the Naver variant and category is exact.
- Verify extracted title/body excludes the edit-notes sentinel and retains every requested content element.
- Show title, content, category, tags, account, and intended images in the native preview.
- Confirm adapter capability before dispatch; reject placeholders or unsupported assets/formatting.
- Check public page and ledger; never infer Naver success from Tistory status or a fixture test.
