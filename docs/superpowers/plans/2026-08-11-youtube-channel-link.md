# YouTube Channel Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record `https://www.youtube.com/@donggu_ai` once in the canonical Obsidian note that owns YouTube channel operations.

**Architecture:** Keep the public account URL in `INDEX - YouTube.md`, separate from per-video `youtube_url` fields and production templates. Make one narrow Markdown edit in an isolated worktree and verify that no unrelated vault file enters the branch.

**Tech Stack:** Obsidian Flavored Markdown, YAML frontmatter, `rg`, Git.

## Global Constraints

- Follow `Personal Branding/_GUIDES/RULES.md` as the vault source of truth.
- The canonical account URL is exactly `https://www.youtube.com/@donggu_ai`.
- Do not add `persona`, `audience`, or any other deprecated frontmatter field.
- Do not add the channel URL to `TPL - Video Build`, a `youtube_url` field, or an individual video note.
- Do not modify `INDEX - Channels.md` or `VOICE - YouTube.md`; both have user changes in the main worktree.
- Do not stash, reset, checkout, stage, or commit any unrelated vault change.
- The branch diff must contain exactly one note.

## File Structure

- Modify `Personal Branding/40_Channel_Packs/YouTube/INDEX - YouTube.md`: update the note date and add the one canonical channel-account section.
- Persist no test file; use explicit shell assertions as the RED/GREEN contract for this Markdown-only change.

---

### Task 1: Add the canonical YouTube account link

**Files:**
- Modify: `Personal Branding/40_Channel_Packs/YouTube/INDEX - YouTube.md`
- Test: shell assertions against the canonical note and template tree

**Interfaces:**
- Consumes: the existing YouTube operations index and its `updated` frontmatter field.
- Produces: one human-readable `@donggu_ai` account link without changing per-video URL semantics.

- [ ] **Step 1: Run the exact URL assertion and verify RED**

Run from the vault root:

```bash
note='Personal Branding/40_Channel_Packs/YouTube/INDEX - YouTube.md'
actual=$(rg -F -c 'https://www.youtube.com/@donggu_ai' "$note" || true)
test "${actual:-0}" -eq 1
```

Expected: exit `1` because the exact URL occurs zero times.

- [ ] **Step 2: Make the minimal canonical-note edit**

Change the frontmatter date:

```yaml
updated: 2026-08-11
```

Insert this section immediately after the opening blockquote and before `## 3레이어`:

```markdown
## 채널 계정

- 공개 채널: [@donggu_ai](https://www.youtube.com/@donggu_ai)
```

Do not change any other line.

- [ ] **Step 3: Run the GREEN content and scope assertions**

Run:

```bash
note='Personal Branding/40_Channel_Packs/YouTube/INDEX - YouTube.md'
actual=$(rg -F -c 'https://www.youtube.com/@donggu_ai' "$note" || true)
test "${actual:-0}" -eq 1
rg -F -- '- 공개 채널: [@donggu_ai](https://www.youtube.com/@donggu_ai)' "$note"
rg -F -- 'updated: 2026-08-11' "$note"
test -z "$(rg -l -F 'https://www.youtube.com/@donggu_ai' 'Personal Branding/70_Templates' || true)"
test "$(git diff --name-only)" = "$note"
git diff --check
```

Expected: every assertion exits `0`, `git diff --name-only` prints only the canonical note, and diff check produces no output.

- [ ] **Step 4: Inspect the exact diff**

Run:

```bash
git diff -- "$note"
```

Expected: one date replacement and the three-line channel-account section, with no other content change.

- [ ] **Step 5: Commit the isolated note change**

```bash
git add -- "$note"
git commit -m "docs(youtube): add canonical channel account"
git status --short
```

Expected: commit succeeds and the worktree is clean.

## Branch Acceptance

Before handing the branch back, repeat the Step 3 assertions against `HEAD`, then run:

```bash
git show --stat --oneline HEAD
git diff HEAD^ --name-only
```

Expected: the commit contains exactly `Personal Branding/40_Channel_Packs/YouTube/INDEX - YouTube.md`.
