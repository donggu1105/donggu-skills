# Simplify SNS Skill Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release `donggu-sns` `2.8.0` with exactly four public skills by removing stock search, card-news generation, and CapCut Shorts generation while preserving AI-image, authoring, YouTube planning, and gated publishing behavior.

**Architecture:** Keep the existing shared Claude/Hermes/Codex `skills/` tree and delete the three unwanted skill directories from it. Repair the remaining live skill routes, relocate the generic image uploader under `publish-sns`, synchronize release metadata, and prove the reduced surface with repository contracts plus before/after agent scenarios.

**Tech Stack:** Markdown skills, JSON/YAML plugin manifests, Python standard-library `unittest`, Codex plugin validator, Claude marketplace validator.

## Global Constraints

- The remaining public skills are exactly `get-ai-image`, `publish-sns`, `writing-social-content`, and `youtube`.
- Remove `get-stock-image`, `make-insta-card-news`, and `make-shorts` from the shared skill tree; do not hide them on only one runtime.
- Image sourcing is exactly user-provided images first, then `get-ai-image` when AI generation is appropriate.
- `publish-sns` publishes finalized text and finalized images; it does not create card layouts or Shorts artifacts.
- Move the generic ordered Supabase uploader to `donggu-sns/skills/publish-sns/upload_images.py` before deleting the card-news directory.
- Tistory/Maily image preparation, publishing receipts, later-turn approval, Maily confirmation, ledger behavior, and native runtime code remain unchanged.
- `youtube` keeps Longform and Shorts-candidate planning but does not promise CapCut or finished-video artifact generation.
- Public personas remain exactly `FDE` and `1인 빌더`; `DA` remains Wishket-internal; `AX Engineer` remains shared expertise rather than a persona; audience stays independent per draft.
- Synchronize all `donggu-sns` distribution versions to exactly `2.8.0`.
- Historical plans/specs remain unchanged.
- Do not modify the Obsidian vault, other plugins, or publishing runtime code.
- No new dependencies.

## File Structure

- Delete `donggu-sns/skills/get-stock-image/`: retired stock-search skill and helper.
- Delete `donggu-sns/skills/make-insta-card-news/`: retired card-news skill and card-specific helpers after moving the generic uploader.
- Delete `donggu-sns/skills/make-shorts/`: retired CapCut/TTS skill and helpers.
- Create `donggu-sns/skills/publish-sns/upload_images.py`: relocated generic uploader for finalized local images.
- Modify the four remaining `SKILL.md` files that currently route to removed skills.
- Modify `donggu-sns/skills/get-ai-image/gen_image.py`: remove the retired stock-skill comparison from the live module documentation.
- Modify `donggu-sns/README.md`: publish the exact four-skill surface and its boundaries.
- Modify the five version-bearing catalog/manifest files and Claude discovery metadata.
- Modify `tests/test_native_plugin_packages.py`: lock the exact surface, live-reference absence, uploader relocation, and version parity.

---

### Task 1: Release the four-skill SNS package

**Files:**
- Delete: `donggu-sns/skills/get-stock-image/SKILL.md`
- Delete: `donggu-sns/skills/get-stock-image/get_stock.py`
- Delete: `donggu-sns/skills/make-insta-card-news/SKILL.md`
- Delete: `donggu-sns/skills/make-insta-card-news/card-template.html`
- Delete: `donggu-sns/skills/make-insta-card-news/commons_fetch.py`
- Delete: `donggu-sns/skills/make-insta-card-news/image-handling.md`
- Delete: `donggu-sns/skills/make-insta-card-news/kr-card-principles.md`
- Delete: `donggu-sns/skills/make-insta-card-news/layout-recipes.md`
- Delete: `donggu-sns/skills/make-insta-card-news/pexels_fetch.py`
- Move: `donggu-sns/skills/make-insta-card-news/supabase_upload.py` → `donggu-sns/skills/publish-sns/upload_images.py`
- Delete: `donggu-sns/skills/make-shorts/SKILL.md`
- Delete: `donggu-sns/skills/make-shorts/capcut_draft.py`
- Delete: `donggu-sns/skills/make-shorts/tts.py`
- Modify: `donggu-sns/skills/get-ai-image/SKILL.md`
- Modify: `donggu-sns/skills/get-ai-image/gen_image.py`
- Modify: `donggu-sns/skills/writing-social-content/SKILL.md`
- Modify: `donggu-sns/skills/publish-sns/SKILL.md`
- Modify: `donggu-sns/skills/youtube/SKILL.md`
- Modify: `donggu-sns/README.md`
- Modify: `.agents/plugins/marketplace.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `donggu-sns/.claude-plugin/plugin.json`
- Modify: `donggu-sns/.codex-plugin/plugin.json`
- Modify: `donggu-sns/plugin.yaml`
- Test: `tests/test_native_plugin_packages.py`

**Interfaces:**
- Consumes: the approved design at `docs/superpowers/specs/2026-08-11-sns-skill-surface-simplification-design.md`, current seven-skill package version `2.7.7`, and the generic uploader's existing CLI contract `python3 <script> <channel> <topic-slug> <bucket> file1 ...`.
- Produces: shared package version `2.8.0`, exact skill set `get-ai-image | publish-sns | writing-social-content | youtube`, and relocated uploader `publish-sns/upload_images.py` with the same ordered `image_urls` JSON result.

- [ ] **Step 1: Write the failing package and live-route contracts**

In `tests/test_native_plugin_packages.py`, change the hard-coded SNS version assertions from `2.7.7` to `2.8.0`, change the expected skill list to the following exact value, and add the new test method below to `NativePluginPackageTests`:

```python
        self.assertEqual(
            [
                "get-ai-image",
                "publish-sns",
                "writing-social-content",
                "youtube",
            ],
            sorted(path.parent.name for path in (package / "skills").glob("*/SKILL.md")),
        )
```

```python
    def test_sns_live_surface_excludes_removed_asset_skills(self):
        package = ROOT / "donggu-sns"
        removed = ("get-stock-image", "make-insta-card-news", "make-shorts")

        for skill_name in removed:
            self.assertFalse((package / "skills" / skill_name).exists())

        live_files = [
            package / "README.md",
            package / ".claude-plugin" / "plugin.json",
            package / ".codex-plugin" / "plugin.json",
        ]
        live_files.extend(
            path
            for path in (package / "skills").rglob("*")
            if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml", ".yml"}
        )
        for path in live_files:
            text = path.read_text(encoding="utf-8")
            for skill_name in removed:
                with self.subTest(path=path, skill_name=skill_name):
                    self.assertNotIn(skill_name, text)

        claude = json.loads(
            (package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        retired_keywords = {
            "card-news",
            "카드뉴스",
            "stock-image",
            "unsplash",
            "pexels",
            "pixabay",
            "free-image",
        }
        self.assertTrue(retired_keywords.isdisjoint(claude["keywords"]))

        readme = (package / "README.md").read_text(encoding="utf-8")
        self.assertIn("skills-4", readme)
        self.assertIn("사용자 제공 이미지", readme)
        self.assertIn("get-ai-image", readme)

        uploader = package / "skills" / "publish-sns" / "upload_images.py"
        self.assertTrue(uploader.is_file())
        uploader_text = uploader.read_text(encoding="utf-8")
        self.assertIn("SUPABASE_URL", uploader_text)
        self.assertIn("image_urls", uploader_text)
        self.assertNotIn("card-news", uploader_text)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_claude_and_hermes_manifests_share_identity_and_version \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_codex_marketplace_exposes_only_sns_from_existing_domain_path \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_codex_manifest_reuses_all_skills_and_matches_release_versions \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_live_surface_excludes_removed_asset_skills \
  -v
```

Expected: FAIL because the package is still `2.7.7`, the three retired directories still exist, the README still reports seven skills, and `publish-sns/upload_images.py` does not exist.

- [ ] **Step 3: Preserve the generic uploader and remove the three skill directories**

Move the uploader without changing its CLI arguments or JSON result:

```bash
git mv \
  donggu-sns/skills/make-insta-card-news/supabase_upload.py \
  donggu-sns/skills/publish-sns/upload_images.py
```

Change only its public naming copy to:

```python
"""Upload finalized local image files to Supabase Storage in stable order.

Path convention:
  <channel>/<YYYY>/<MM-DD>/<topic-slug>-<HHMMSS>/<NN><ext>

Usage:
  python3 upload_images.py <channel> <topic-slug> <bucket> file1.png file2.png ...

The input order is preserved in the returned ``image_urls`` JSON array.
"""
```

Then remove these exact directories:

```bash
git rm -r -- \
  donggu-sns/skills/get-stock-image \
  donggu-sns/skills/make-insta-card-news \
  donggu-sns/skills/make-shorts
```

- [ ] **Step 4: Repair the four remaining skill contracts**

Apply these exact behavior changes, preserving unrelated content:

```text
get-ai-image/SKILL.md
- Describe one AI-generated representative image or illustration for Blog/SNS.
- State: existing user screenshots/assets are first choice; otherwise generate with this skill.
- State: never fabricate a factual depiction of a real person, place, customer, product state, or event.
- Do not route cards, stock search, or text-heavy visual composition to another donggu-sns skill.
- Keep publish-sns as the upload/publishing handoff.

get-ai-image/gen_image.py
- Replace the get-stock-image comparison in the module docstring with a standalone
  prompt -> saved file + one-line JSON contract.

writing-social-content/SKILL.md
- Keep authoring limited to Blog, LinkedIn, Threads, and Maily.
- For images, prefer user-provided assets and otherwise route only to get-ai-image.
- Treat Instagram card/carousel construction and finished video creation as outside this skill.
- Route YouTube planning only to youtube.
- Remove all three retired skill names from When NOT, Related Skills, and every live route.

publish-sns/SKILL.md
- Keep preview -> later-turn approval -> dispatch and all ledger safety rules unchanged.
- For factual real-world images, require a supplied/verified asset instead of AI fabrication.
- Remove card-format ownership, render-webhook creation, and Shorts-production routes.
- Missing text-channel drafts may route to writing-social-content; Instagram requires a finalized
  caption plus finalized image files rather than a generated card deck.
- Threads/Instagram finalized local images use publish-sns/upload_images.py and then image_urls.
- Remove the render webhook row; keep the existing publishing webhook rows.
- Replace make-* red-flag wording with the matching remaining authoring/image path.

youtube/SKILL.md
- Keep Longform and Shorts-candidate planning.
- Say explicitly that finished Shorts/video files and CapCut drafts are outside this skill and are
  executed by the user or an external editor.
- Remove the retired Shorts skill from routing and Related Skills.
```

- [ ] **Step 5: Update current README and discovery metadata**

Make `donggu-sns/README.md` expose exactly this table:

```markdown
| Skill | 사용 시점 | Output |
|---|---|---|
| **writing-social-content** | Blog·LinkedIn·Threads·Maily 텍스트 작성·변환 | 채널별 확정 초안 |
| **youtube** | YouTube Longform + Shorts 후보 기획·회고 | 영상 Pack |
| **publish-sns** | tistory·maily·threads·linkedin·instagram 발행·삭제 | 발행 결과 + ledger |
| **get-ai-image** | 사용자 이미지가 없을 때 대표이미지·삽화 생성 | 이미지 파일 |
```

Also change the badge to `skills-4`, replace the post-authoring route with:

```text
텍스트 확정
├── 파일 저장 요청 → target-native 파일 도구
├── 이미지 요청    → 사용자 제공 이미지 / get-ai-image
├── 영상 기획      → youtube
└── 게시 요청      → publish-sns preview·approval
```

Remove the retired Playwright, `edge-tts`, and `pyCapCut` dependencies. Keep the publishing-adapter dependencies and document any existing `get-ai-image` backend requirements without adding a dependency.

In `donggu-sns/.claude-plugin/plugin.json`, remove exactly these retired keywords:

```json
[
  "card-news",
  "카드뉴스",
  "stock-image",
  "unsplash",
  "pexels",
  "pixabay",
  "free-image"
]
```

Keep `instagram`, `shorts`, and `youtube` because the plugin still publishes Instagram and plans YouTube Shorts candidates. Change the current Claude marketplace description from visual-artifact production to AI-image generation and YouTube planning.

- [ ] **Step 6: Synchronize release version `2.8.0`**

Change only the `donggu-sns` version in these exact files:

```text
.agents/plugins/marketplace.json          2.7.7 -> 2.8.0
.claude-plugin/marketplace.json           2.7.7 -> 2.8.0
donggu-sns/.claude-plugin/plugin.json     2.7.7 -> 2.8.0
donggu-sns/.codex-plugin/plugin.json      2.7.7 -> 2.8.0
donggu-sns/plugin.yaml                    2.7.7 -> 2.8.0
```

Do not change another plugin's version.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run the exact Step 2 command again.

Expected: all four selected tests pass and the output contains no failures.

- [ ] **Step 8: Run current-surface and persona regression tests**

Run:

```bash
python3 -m unittest \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_claude_marketplace_versions_match_dual_harness_packages \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_codex_install_docs_name_marketplace_plugin_and_new_thread_boundary \
  tests.test_obsidian_content_flow_contracts.ObsidianContentFlowContractsTest.test_writing_persona_reference_has_exact_public_choices \
  tests.test_obsidian_content_flow_contracts.ObsidianContentFlowContractsTest.test_writing_persona_release_boundaries_are_explicit \
  -v
```

Expected: all selected tests pass; personas and the installation/new-thread boundary remain unchanged.

- [ ] **Step 9: Run full validation**

Run:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -q
uv run --with pyyaml python \
  '/Users/joeykang/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py' \
  donggu-sns
claude plugin validate .
git diff --check
```

Expected: the Python suite reports `OK`, the Codex validator passes, the Claude validator passes, and `git diff --check` produces no output. Existing full-suite `ResourceWarning` output may be reported but must not be described as pristine.

- [ ] **Step 10: Verify live reference absence**

Run:

```bash
rg -n --hidden \
  --glob '!docs/superpowers/**' \
  --glob '!docs/specs/**' \
  --glob '!**/.git/**' \
  'get-stock-image|make-insta-card-news|make-shorts' \
  donggu-sns .agents .claude-plugin
```

Expected: no output. Tests and historical plan/spec files necessarily name the retired skills to enforce or document their removal and are outside this live-surface scan.

- [ ] **Step 11: Commit the implementation**

Review the exact staged paths, then commit:

```bash
git add -- \
  .agents/plugins/marketplace.json \
  .claude-plugin/marketplace.json \
  donggu-sns \
  tests/test_native_plugin_packages.py
git diff --cached --check
git commit -m "refactor(sns): reduce public skill surface"
```

The implementer report must include the RED failure, GREEN result, full-suite count, validator results, live-reference scan, changed files, and self-review findings.

---

## Controller verification after Task 1 review

The controller performs two gates after the task reviewer approves the commit:

1. Run a fresh-context agent scenario against the revised four-skill package. The answer must use `writing-social-content` for text, `youtube` for planning, user-provided assets or `get-ai-image` for imagery, and `publish-sns` for gated publishing. It must not name a removed skill or promise card-deck/CapCut generation.
2. After local merge, run `codex plugin add donggu-sns@donggu-skills --json`, verify installed version `2.8.0`, verify exactly four cached `SKILL.md` files, and diff the cached `skills/` tree against the source tree.
