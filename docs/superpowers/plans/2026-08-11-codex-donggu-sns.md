# Codex donggu-sns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `donggu-sns` the first Codex-installable plugin in the `donggu-skills` marketplace without duplicating its existing skills.

**Architecture:** Add a repo-local Codex marketplace catalog that exposes only `donggu-sns`, and add a Codex manifest that points at the existing `donggu-sns/skills/` tree. Keep Claude, Hermes, and Codex package metadata versioned together at `2.7.7`; preserve all current skill behavior and persona rules.

**Tech Stack:** JSON plugin manifests, YAML Hermes manifest, Markdown documentation, Python standard-library `unittest`, Codex plugin CLI and plugin-creator validator.

## Global Constraints

- The public persona set remains exactly `FDE` and `1인 빌더`.
- `DA` remains Wishket-internal; `AX Engineer` remains a shared expertise label, not a persona.
- Do not copy skills into `~/.codex/skills` or create Codex-specific `SKILL.md` copies.
- Do not move or duplicate the existing root-level `donggu-<domain>/` plugin directories.
- The Codex marketplace catalog contains only `donggu-sns` in this release but remains appendable for future domain plugins.
- Synchronize every `donggu-sns` distribution version to exactly `2.7.7`.
- Keep existing Claude and Hermes distribution files; do not remove or replace them.
- No new dependencies.

## File Structure

- Create `.agents/plugins/marketplace.json`: repo-local Codex catalog, currently exposing only `donggu-sns`.
- Create `donggu-sns/.codex-plugin/plugin.json`: Codex package identity and shared skill-tree pointer.
- Modify `.claude-plugin/marketplace.json`: synchronize the `donggu-sns` entry to `2.7.7`.
- Modify `donggu-sns/.claude-plugin/plugin.json`: synchronize the Claude package to `2.7.7`.
- Modify `donggu-sns/plugin.yaml`: synchronize the Hermes package to `2.7.7`.
- Modify `tests/test_native_plugin_packages.py`: lock marketplace shape, shared skills, policies, and cross-runtime versions.
- Modify `README.md`: document Codex marketplace and install/update commands without changing other plugins' availability.
- Modify `donggu-sns/README.md`: state Claude/Hermes/Codex surfaces and the new-thread pickup boundary.

---

### Task 1: Codex catalog, plugin manifest, and synchronized release metadata

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Create: `donggu-sns/.codex-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `donggu-sns/.claude-plugin/plugin.json`
- Modify: `donggu-sns/plugin.yaml`
- Test: `tests/test_native_plugin_packages.py`

**Interfaces:**
- Consumes: the existing `donggu-sns/skills/*/SKILL.md` tree and existing Claude/Hermes package metadata.
- Produces: Codex marketplace `donggu-skills`, plugin identity `donggu-sns`, and `skills: "./skills/"` at version `2.7.7`.

- [ ] **Step 1: Write the failing packaging contracts**

Add these methods to `NativePluginPackageTests` near the existing manifest tests, and change the existing hard-coded SNS version assertion from `2.7.6` to `2.7.7`:

```python
    def test_codex_marketplace_exposes_only_sns_from_existing_domain_path(self):
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual("donggu-skills", marketplace["name"])
        self.assertEqual("Donggu Skills", marketplace["interface"]["displayName"])
        self.assertEqual(["donggu-sns"], [item["name"] for item in marketplace["plugins"]])
        entry = marketplace["plugins"][0]
        self.assertEqual({"source": "local", "path": "./donggu-sns"}, entry["source"])
        self.assertEqual("2.7.7", entry["version"])
        self.assertEqual(
            {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            entry["policy"],
        )
        self.assertEqual("Productivity", entry["category"])

    def test_sns_codex_manifest_reuses_all_skills_and_matches_release_versions(self):
        package = ROOT / "donggu-sns"
        codex = json.loads(
            (package / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual("donggu-sns", codex["name"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual("2.7.7", codex["version"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertEqual(codex["version"], manifest_scalar(package / "plugin.yaml", "version"))
        self.assertEqual(codex["version"], marketplace["plugins"][0]["version"])
        self.assertEqual(
            [
                "get-ai-image",
                "get-stock-image",
                "make-insta-card-news",
                "make-shorts",
                "publish-sns",
                "writing-social-content",
                "youtube",
            ],
            sorted(path.parent.name for path in (package / "skills").glob("*/SKILL.md")),
        )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_codex_marketplace_exposes_only_sns_from_existing_domain_path \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_codex_manifest_reuses_all_skills_and_matches_release_versions \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_claude_and_hermes_manifests_share_identity_and_version \
  -v
```

Expected: FAIL because `.agents/plugins/marketplace.json` and `donggu-sns/.codex-plugin/plugin.json` do not exist and the existing release metadata is still `2.7.6`.

- [ ] **Step 3: Add the minimal Codex marketplace**

Create `.agents/plugins/marketplace.json` with exactly:

```json
{
  "name": "donggu-skills",
  "interface": {
    "displayName": "Donggu Skills"
  },
  "plugins": [
    {
      "name": "donggu-sns",
      "source": {
        "source": "local",
        "path": "./donggu-sns"
      },
      "version": "2.7.7",
      "policy": {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL"
      },
      "category": "Productivity"
    }
  ]
}
```

- [ ] **Step 4: Add the Codex plugin manifest**

Create `donggu-sns/.codex-plugin/plugin.json` with the existing Claude keyword list and these binding fields:

```json
{
  "name": "donggu-sns",
  "version": "2.7.7",
  "description": "SNS and YouTube editorial operations with FDE or solo-builder persona routing, artifact creation, and gated publishing.",
  "author": {
    "name": "강동현 (donggu)",
    "url": "https://github.com/donggu1105"
  },
  "repository": "https://github.com/donggu1105/donggu-skills",
  "license": "MIT",
  "keywords": [
    "sns",
    "linkedin",
    "threads",
    "instagram",
    "maily",
    "blog",
    "youtube",
    "fde",
    "solo-builder",
    "content-writing",
    "gated-publishing"
  ],
  "skills": "./skills/",
  "interface": {
    "displayName": "Donggu SNS",
    "shortDescription": "FDE·1인 빌더 관점의 SNS·YouTube 제작과 승인형 발행",
    "longDescription": "FDE와 1인 빌더 중 하나의 관점을 선택해 Blog, LinkedIn, Threads, Maily 글과 YouTube 기획을 만들고 이미지·숏폼 산출물과 승인형 발행 워크플로를 제공합니다.",
    "developerName": "강동현 (donggu)",
    "category": "Productivity",
    "capabilities": ["Read", "Write", "Shell"],
    "defaultPrompt": [
      "FDE 페르소나로 이 내용을 LinkedIn 글로 작성해줘.",
      "1인 빌더 페르소나로 이 소재를 Threads 글로 작성해줘.",
      "이 소재를 YouTube Longform과 Shorts Pack으로 기획해줘."
    ]
  }
}
```

- [ ] **Step 5: Synchronize existing release metadata**

Change only the `donggu-sns` versions:

```text
.claude-plugin/marketplace.json          2.7.6 -> 2.7.7
donggu-sns/.claude-plugin/plugin.json   2.7.6 -> 2.7.7
donggu-sns/plugin.yaml                  2.7.6 -> 2.7.7
```

Do not change other plugin versions or persona content.

- [ ] **Step 6: Run focused tests and plugin validation**

Run:

```bash
python3 -m unittest \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_codex_marketplace_exposes_only_sns_from_existing_domain_path \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_codex_manifest_reuses_all_skills_and_matches_release_versions \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_claude_and_hermes_manifests_share_identity_and_version \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_claude_marketplace_versions_match_dual_harness_packages \
  -v
python3 '/Users/joeykang/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py' donggu-sns
git diff --check
```

Expected: all selected tests pass, the validator exits `0`, and `git diff --check` produces no output.

- [ ] **Step 7: Commit the packaging task**

```bash
git add -- \
  .agents/plugins/marketplace.json \
  .claude-plugin/marketplace.json \
  donggu-sns/.codex-plugin/plugin.json \
  donggu-sns/.claude-plugin/plugin.json \
  donggu-sns/plugin.yaml \
  tests/test_native_plugin_packages.py
git commit -m "feat(sns): package donggu-sns for Codex"
```

---

### Task 2: Codex installation and update documentation

**Files:**
- Modify: `README.md`
- Modify: `donggu-sns/README.md`
- Test: `tests/test_native_plugin_packages.py`

**Interfaces:**
- Consumes: marketplace name `donggu-skills`, plugin name `donggu-sns`, public Git source `donggu1105/donggu-skills`, and the Codex new-thread reload boundary.
- Produces: exact CLI instructions for discovery, install, upgrade, and skill pickup.

- [ ] **Step 1: Write the failing documentation contract**

Add this method to `NativePluginPackageTests`:

```python
    def test_codex_install_docs_name_marketplace_plugin_and_new_thread_boundary(self):
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        sns_readme = (ROOT / "donggu-sns" / "README.md").read_text(encoding="utf-8")
        for text in (root_readme, sns_readme):
            self.assertIn("codex plugin marketplace add donggu1105/donggu-skills", text)
            self.assertIn("codex plugin add donggu-sns@donggu-skills", text)
            self.assertIn("새 thread", text)
        self.assertIn("codex plugin marketplace upgrade donggu-skills", root_readme)
```

- [ ] **Step 2: Run the documentation test and verify RED**

Run:

```bash
python3 -m unittest \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_codex_install_docs_name_marketplace_plugin_and_new_thread_boundary \
  -v
```

Expected: FAIL because neither README currently documents Codex installation.

- [ ] **Step 3: Document the Codex surface in the root README**

Update the opening description so the repository is described as a Claude Code and Codex marketplace. Under Quick Start, retain the existing Claude steps and add this Codex-specific subsection:

````markdown
### Codex — 현재 `donggu-sns` 지원

```bash
codex plugin marketplace add donggu1105/donggu-skills
codex plugin add donggu-sns@donggu-skills
```

업데이트할 때는 marketplace를 갱신한 뒤 plugin을 다시 설치한다.

```bash
codex plugin marketplace upgrade donggu-skills
codex plugin add donggu-sns@donggu-skills
```

설치·업데이트된 skill 목록은 새 thread에서 다시 로드한다. 현재 Codex catalog에는 `donggu-sns`만 등록되어 있으며 나머지 domain plugin은 Claude Code 전용이다.
````

Keep the existing Claude installation instructions intact.

- [ ] **Step 4: Document Codex installation in the SNS README**

Add an `## Install` section before `## Dependencies`:

````markdown
## Install

Claude Code에서는 기존 `donggu-skills` marketplace의 `donggu-sns`를 설치한다. Codex에서는 다음 명령으로 repo marketplace와 plugin을 설치한다.

```bash
codex plugin marketplace add donggu1105/donggu-skills
codex plugin add donggu-sns@donggu-skills
```

설치 후에는 새 thread에서 `donggu-sns`의 skill 목록을 다시 로드한다. Claude와 Codex는 이 디렉터리의 같은 `skills/` 트리를 사용한다.
````

- [ ] **Step 5: Run documentation, focused, and full regression tests**

Run:

```bash
python3 -m unittest \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_codex_install_docs_name_marketplace_plugin_and_new_thread_boundary \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_codex_marketplace_exposes_only_sns_from_existing_domain_path \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_codex_manifest_reuses_all_skills_and_matches_release_versions \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_claude_and_hermes_manifests_share_identity_and_version \
  -v
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 '/Users/joeykang/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py' donggu-sns
git diff --check
```

Expected: all tests pass, validator exits `0`, and diff check is clean.

- [ ] **Step 6: Commit the documentation task**

```bash
git add -- README.md donggu-sns/README.md tests/test_native_plugin_packages.py
git commit -m "docs(sns): document Codex installation"
```

## Branch Acceptance

Before handing the branch back, run:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -q
python3 '/Users/joeykang/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py' donggu-sns
claude plugin validate .
git diff --check
git status --short
```

Expected: full suite passes; both plugin validators exit `0`; diff check is clean; status contains no uncommitted task files.
