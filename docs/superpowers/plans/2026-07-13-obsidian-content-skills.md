# Obsidian Content Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 동구님의 content-first 작성·발행·역분해 흐름에 맞춰 Obsidian/SNS portable skill의 책임 경계와 스키마를 일관되게 정리한다.

**Architecture:** Inbox는 자유 캡처로 유지하고, `writing-social-content`가 origin/adapt 작성 계보를 소유하며, `publish-sns`는 발행과 장부까지만 담당한다. routine CORE 후보는 `extract-core`, canon 깊은 역분해는 `decompose-canon`, 일일 흐름 검사는 `checking-vault-health`, 중복 검사는 `finding-duplicate-notes`, 파일 적용은 `core-review-approval`로 분리한다.

**Tech Stack:** Markdown SKILL.md, Python unittest contract checks, Claude plugin manifests.

## Global Constraints

- Vault 폴더 구조를 바꾸지 않는다.
- `00_Inbox` 자동 이동·삭제·분류·수정 금지.
- AI 뉴스/FDE 리서치 파일을 건드리지 않는다.
- 자동화는 검사·후보화까지만 수행하고 Vault 변경은 후보 ID별 승인 계약을 따른다.
- `writing-social-content`의 저장 type은 `channel_pack`이다.
- 실제 첫 채널은 고정하지 않으며 `derived_from`은 계보이지 master hierarchy가 아니다.
- plugin version과 marketplace version은 변경된 plugin마다 함께 올린다.

---

### Task 1: Cross-skill contract RED tests

**Files:**
- Create: `tests/test_obsidian_content_flow_contracts.py`
- Read: `donggu-obsidian/skills/*/SKILL.md`
- Read: `donggu-sns/skills/{writing-social-content,publish-sns}/SKILL.md`

**Interfaces:**
- Consumes: SKILL.md text and plugin manifests.
- Produces: critical workflow invariants expressed as executable assertions.

- [ ] **Step 1: Write failing tests**

Add unittest cases that assert:

```python
self.assertIn("origin", writing)
self.assertIn("adapt", writing)
self.assertIn("type: channel_pack", writing)
self.assertIn("derived_from", writing)
self.assertNotIn("type: content", writing)
self.assertIn("발행 완료 이벤트", publishing)
self.assertIn("routine", extract_core.lower())
self.assertIn("canon", decompose.lower())
self.assertIn("후보가 없어도", health)
self.assertIn("00_Inbox", health)
self.assertIn("자동 이동", health)
```

Also assert that only `core-review-approval` describes applying a candidate and that no audited skill grants automatic Vault mutation.

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
```

Expected: failures for missing origin/adapt, `type: content`, and daily notification contract.

- [ ] **Step 3: Keep tests scoped**

Use exact skill paths and semantic assertions; do not snapshot whole documents or assert incidental prose.

### Task 2: Writing and publishing boundary

**Files:**
- Modify: `donggu-sns/skills/writing-social-content/SKILL.md`
- Modify: `donggu-sns/skills/publish-sns/SKILL.md`
- Modify: `donggu-sns/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: Inbox/Source/Channel Pack notes.
- Produces: origin/adapt channel notes and publish ledger/event boundary.

- [ ] **Step 1: Implement `origin` and `adapt` modes**

Document:

```yaml
type: channel_pack
derived_from: "[[optional exact source Channel Pack]]"
related: ["[[other same-topic Channel Pack]]"]
```

`origin` creates the first channel note from raw material. `adapt` reads one existing Channel Pack and rewrites it using the destination channel VOICE. `derived_from` records lineage only; every final body remains channel-native.

- [ ] **Step 2: Remove conflicting rules**

Delete `type: content` and the absolute “no source lineage” wording. Preserve the rule that channels do not share one mechanically published master body.

- [ ] **Step 3: Tighten `publish-sns`**

State that successful `published_posts` persistence creates the post-publication review event through the existing DB trigger. Publishing does not create CORE/Snippet/MOC directly. Failed or dry-run publications must not create a review event.

- [ ] **Step 4: Bump donggu-sns plugin version**

Increment patch version in plugin and marketplace manifests to the same value.

- [ ] **Step 5: Run focused tests**

```bash
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
claude plugin validate .
```

Expected: writing/publishing cases PASS.

### Task 3: Routine extraction and canon decomposition boundary

**Files:**
- Modify: `donggu-obsidian/skills/extract-core/SKILL.md`
- Modify: `donggu-obsidian/skills/decompose-canon/SKILL.md`

**Interfaces:**
- Consumes: published event metadata and approved canon posts.
- Produces: routine CORE candidates or deep canon decomposition proposals.

- [ ] **Step 1: Make `extract-core` routine-first**

Set priority:

```text
1. newly published Channel Pack
2. curated 10_Sources note
3. explicit Inbox recommendation-only request
```

Keep Inbox read-only and recommendation-only. Require existing CORE search and `LINK/NEW/MERGE/HOLD` outcome before persistence.

- [ ] **Step 2: Keep `decompose-canon` deep-only**

Clarify that routine published posts are handled by `extract-core`; `decompose-canon` runs only after explicit canon selection and may propose a small set of CORE/Snippet atoms.

- [ ] **Step 3: Verify RED tests turn GREEN**

```bash
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
```

Expected: extraction/decomposition boundary cases PASS.

### Task 4: Daily health and duplicate boundary

**Files:**
- Modify: `donggu-obsidian/skills/checking-vault-health/SKILL.md`
- Modify: `donggu-obsidian/skills/finding-duplicate-notes/SKILL.md`
- Modify: `donggu-obsidian/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: metadata-all + representative content sample.
- Produces: daily read-only metrics and report-only candidates.

- [ ] **Step 1: Add daily contract**

Require daily health output even when candidate count is zero. Metrics: recent Inbox count, recent published count, stalled Source count, return-gap count, link/schema candidate count.

- [ ] **Step 2: Preserve Inbox boundary**

Explicitly prohibit candidate generation from Inbox age/count alone. Inbox content can be used only for aggregate entry health or explicit recommendation-only review.

- [ ] **Step 3: Make duplicate audit monthly/on-demand**

Prevent daily semantic duplicate scanning of the full Vault. Daily care may report a threshold signal; the full five-pattern audit runs monthly or on explicit request.

- [ ] **Step 4: Bump donggu-obsidian plugin version**

Increment patch version in plugin and marketplace manifests to the same value.

- [ ] **Step 5: Verify**

```bash
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
python3 -m unittest discover -s donggu-obsidian/skills/core-review-approval/tests -p 'test_*.py' -q
claude plugin validate .
```

Expected: contract suite and existing 47 helper tests PASS.

### Task 5: Final repository verification and commit

**Files:** all files modified by Tasks 1–4.

- [ ] **Step 1: Check scope and secrets**

```bash
git diff --check
git status --short
```

Verify no AI-news/FDE files, env files, credentials, or unrelated paths are changed.

- [ ] **Step 2: Run final suite**

```bash
python3 -m unittest tests.test_obsidian_content_flow_contracts -v
python3 -m unittest discover -s donggu-obsidian/skills/core-review-approval/tests -p 'test_*.py' -q
claude plugin validate .
```

- [ ] **Step 3: Commit scoped changes**

```bash
git add tests/test_obsidian_content_flow_contracts.py donggu-sns/skills/writing-social-content/SKILL.md donggu-sns/skills/publish-sns/SKILL.md donggu-sns/.claude-plugin/plugin.json donggu-obsidian/skills/extract-core/SKILL.md donggu-obsidian/skills/decompose-canon/SKILL.md donggu-obsidian/skills/checking-vault-health/SKILL.md donggu-obsidian/skills/finding-duplicate-notes/SKILL.md donggu-obsidian/.claude-plugin/plugin.json .claude-plugin/marketplace.json docs/superpowers/plans/2026-07-13-obsidian-content-skills.md
git commit -m "♻️ refactor: 콘텐츠 우선 Vault 스킬 경계를 정리한다"
```

- [ ] **Step 4: Report commit SHA and exact test counts**
