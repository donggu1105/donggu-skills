# SNS Skill Surface Simplification Design

## Goal

Reduce `donggu-sns` from seven public skills to four by removing:

- `get-stock-image`
- `make-insta-card-news`
- `make-shorts`

The remaining public skills are exactly:

- `get-ai-image`
- `publish-sns`
- `writing-social-content`
- `youtube`

Image sourcing becomes intentionally narrow: use an image supplied by the user first, or generate one with `get-ai-image`. The package no longer searches stock libraries, creates card-news decks, or assembles CapCut Shorts drafts.

## Decision

Three approaches were considered.

1. **Delete all three skills and repair every live route — selected.** This produces the smallest honest public surface and removes helpers and dependencies that are no longer part of the workflow.
2. **Remove only card-news and Shorts while keeping stock search.** This preserves factual-image search, but retains a skill the user does not use and keeps the image-routing surface larger than necessary.
3. **Hide the three skills only from Codex.** This would make Claude, Hermes, and Codex disagree and violate the shared-skill-tree contract.

The selected approach keeps one shared `skills/` tree across Claude, Hermes, and Codex and deletes the three directories from that tree.

## Public behavior

### Authoring

`writing-social-content` continues to own Blog, LinkedIn, Threads, and Maily text. It no longer routes card creation, stock search, or Shorts production to removed skills.

For images it states one rule:

1. prefer user-provided screenshots or assets;
2. otherwise use `get-ai-image` when an AI-generated image is appropriate.

It does not gain Instagram authoring, card composition, video editing, or publishing responsibilities.

### AI images

`get-ai-image` remains a single-image generator for Blog and SNS representative images or illustrations. Its documentation must stand alone: it cannot describe itself as the AI counterpart to stock search or route text-heavy cards to the removed card-news skill.

User-provided assets remain the first choice when they already show the real result. AI generation must not fabricate a factual depiction of a real person, place, customer, product state, or event.

### Publishing

`publish-sns` remains the only gated mutation surface. It publishes finalized text and finalized images; it no longer creates card layouts or Shorts artifacts.

- Tistory and Maily keep the existing `prepare_blog_images.py` flow.
- Threads and Instagram accept final user-provided or AI-generated local images.
- The generic ordered Supabase uploader currently stored under `make-insta-card-news/supabase_upload.py` moves under `publish-sns` and is renamed to describe image upload rather than card generation.
- Card render-webhook instructions and card-specific format ownership are removed from the live skill documentation.
- Instagram still requires `image_urls` plus a caption and retains preview/approval/ledger safety gates.

No native publishing adapter operation, receipt rule, approval rule, or ledger behavior changes.

### YouTube

`youtube` continues to plan Longform episodes and evaluate Shorts candidates. It no longer promises CapCut draft creation. An approved Shorts candidate remains a production plan that the user or an external editor can execute.

Transcript, thumbnail, safety, analytics, and CORE-reconciliation contracts remain unchanged.

### Persona and channel contracts

The public personas remain exactly `FDE` and `1인 빌더`. `DA` remains Wishket-internal, and `AX Engineer` remains shared expertise rather than a third persona. Audience selection remains independent per draft. Removing asset skills does not change channel availability or persona resolution.

## Package and release

All live package surfaces move together to version `2.8.0`:

- `.agents/plugins/marketplace.json`
- `.claude-plugin/marketplace.json` (`donggu-sns` entry only)
- `donggu-sns/.claude-plugin/plugin.json`
- `donggu-sns/.codex-plugin/plugin.json`
- `donggu-sns/plugin.yaml`

Claude metadata removes card-news, Shorts-production, stock-image, and stock-provider discovery keywords. Current public README copy changes from seven skills to four and removes obsolete runtime dependencies.

Historical plans and specs remain unchanged because they document the releases that originally shipped those surfaces. The new design and current live contracts supersede them.

After integration, reinstall `donggu-sns@donggu-skills` and verify the Codex cache contains version `2.8.0` with exactly the four remaining skills. A new Codex thread is required to load the reduced skill list.

## File changes

Delete the complete directories:

- `donggu-sns/skills/get-stock-image/`
- `donggu-sns/skills/make-insta-card-news/`
- `donggu-sns/skills/make-shorts/`

Move the generic uploader before deleting the card-news directory:

- from `donggu-sns/skills/make-insta-card-news/supabase_upload.py`
- to `donggu-sns/skills/publish-sns/upload_images.py`

Update live references in:

- `donggu-sns/skills/get-ai-image/SKILL.md`
- `donggu-sns/skills/writing-social-content/SKILL.md`
- `donggu-sns/skills/publish-sns/SKILL.md`
- `donggu-sns/skills/youtube/SKILL.md`
- `donggu-sns/README.md`
- the five version-bearing manifests/catalogs
- `tests/test_native_plugin_packages.py`

Do not change publishing runtime code, persona references, channel style references, the Obsidian vault, or other plugins.

## Verification

The implementation uses RED-GREEN-REFACTOR.

1. Change the package contract test to expect the exact four-skill list and version `2.8.0`; add assertions that removed names do not occur in live remaining skill documents or current package metadata. Run it before production changes and confirm it fails for the old seven-skill surface.
2. Add a baseline agent scenario using the old guidance and record that it routes an image/card/Shorts request to at least one removed skill. Re-run the equivalent scenario with the revised remaining skills and require user assets or `get-ai-image` for images, no removed skill names, and no promise of card or CapCut artifact generation.
3. Delete the three skill directories, move the generic uploader, repair live routes, metadata, README, and synchronized versions.
4. Run focused packaging/persona/publishing contract tests, the full Python test suite, Codex plugin validation, Claude marketplace validation, `git diff --check`, and a repository scan that excludes historical specs/plans but finds no live reference to removed skills.
5. After local merge, reinstall the plugin and verify `codex plugin list` reports `donggu-sns@donggu-skills` version `2.8.0`, enabled, with an installed cache whose `skills/` tree exactly matches the four source skills.

## Success criteria

- Claude, Hermes, and Codex share exactly four `donggu-sns` skills.
- None of the three removed skill directories or executable helpers remain, except the generic uploader relocated under `publish-sns`.
- No remaining live skill routes to a removed skill.
- User-provided images and `get-ai-image` are the only documented image-source paths.
- Publishing safety and persona contracts remain unchanged.
- Tests and validators pass, and the installed Codex cache matches source version `2.8.0`.
