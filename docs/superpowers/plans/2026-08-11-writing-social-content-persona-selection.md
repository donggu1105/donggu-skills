# Writing Social Content Persona Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add explicit `FDE` versus `1인 빌더` author-persona resolution to `writing-social-content` without tying either persona to a channel or exposing Wishket's internal `DA` role.

**Architecture:** Keep `SKILL.md` as the authoring router and add one bundled, portable `references/personas.md` as the persona contract. Resolve exactly one persona before source locking, resolve audience independently per draft, and retain `common-voice.md` plus channel references as the voice and format authorities.

**Tech Stack:** Markdown skill contracts, Python `unittest` contract tests, Claude plugin JSON, Hermes YAML.

## Global Constraints

- Public persona options are exactly `FDE` and `1인 빌더`.
- `DA` remains internal to Wishket and is not offered as a public persona.
- `AX Engineer` is shared expertise language, not a third persona.
- Blog, LinkedIn, Threads, and Maily remain available to both personas.
- Audience is selected per draft and is not hard-coded by persona or channel.
- Persona framing may not add unsupported experience, customer detail, outcomes, launches, revenue, or business success.
- The skill remains portable and must not read the Obsidian vault at runtime.
- No new dependencies.

---

### Task 1: Lock the persona contract with failing tests

**Files:**
- Modify: `tests/test_obsidian_content_flow_contracts.py:17-27`
- Modify: `tests/test_obsidian_content_flow_contracts.py:42-157`

**Interfaces:**
- Consumes: existing `SKILL_PATHS`, `WRITING_REFERENCE_PATHS`, and `ObsidianContentFlowContractsTest` helpers.
- Produces: contract coverage for reference packaging, selection order, two-option identity, audience independence, portability, and public-role boundaries.

- [ ] **Step 1: Register the missing persona reference in the fixture map**

Add this entry at the start of `WRITING_REFERENCE_PATHS`:

```python
"personas": REPO_ROOT / "donggu-sns" / "skills" / "writing-social-content" / "references" / "personas.md",
```

- [ ] **Step 2: Add failing persona-selection contract tests**

Add these methods to `ObsidianContentFlowContractsTest`:

```python
def test_writing_resolves_one_persona_before_source_lock(self):
    writing = self.skills["writing"]

    self.assertIn("references/personas.md", writing)
    self.assertIn("### 0. 발신 페르소나와 오디언스 잠금", writing)
    self.assertLess(
        writing.index("### 0. 발신 페르소나와 오디언스 잠금"),
        writing.index("### 1. 범위와 source 잠금"),
    )
    self.assertIn("명시했으면 다시 묻지 않는다", writing)
    self.assertIn("정확히 하나", writing)
    self.assertIn("오디언스", writing)
    self.assertIn("채널에 고정하지 않는다", writing)

def test_writing_persona_reference_has_exact_public_choices(self):
    personas = self.writing_references["personas"]

    self.assertIn("## FDE", personas)
    self.assertIn("## 1인 빌더", personas)
    self.assertIn("공개 페르소나 선택지는 정확히 두 개", personas)
    self.assertIn("DA는 위시켓 내부 역할", personas)
    self.assertIn("AX Engineer", personas)
    self.assertIn("세 번째 페르소나", personas)
    self.assertIn("모든 지원 채널", personas)
    self.assertIn("오디언스는 글마다", personas)

def test_writing_persona_reference_preserves_evidence_boundaries(self):
    personas = self.writing_references["personas"]

    self.assertIn("고객·회사 식별정보", personas)
    self.assertIn("수익", personas)
    self.assertIn("출시", personas)
    self.assertIn("근거가 있을 때만", personas)
    self.assertIn("주 페르소나", personas)
    self.assertNotIn("Personal Branding/", personas)
    self.assertNotIn("/Users/", personas)
    self.assertNotIn("[[", personas)
```

- [ ] **Step 3: Run the new tests and verify the missing reference fails first**

Run:

```bash
python -m unittest \
  tests.test_obsidian_content_flow_contracts.ObsidianContentFlowContractsTest.test_writing_resolves_one_persona_before_source_lock \
  tests.test_obsidian_content_flow_contracts.ObsidianContentFlowContractsTest.test_writing_persona_reference_has_exact_public_choices \
  tests.test_obsidian_content_flow_contracts.ObsidianContentFlowContractsTest.test_writing_persona_reference_preserves_evidence_boundaries
```

Expected: `ERROR` during `setUpClass` because `references/personas.md` does not exist.

- [ ] **Step 4: Commit the failing contract**

```bash
git add tests/test_obsidian_content_flow_contracts.py
git commit -m "test(sns): lock persona selection contract"
```

---

### Task 2: Add the portable persona reference and router workflow

**Files:**
- Create: `donggu-sns/skills/writing-social-content/references/personas.md`
- Modify: `donggu-sns/skills/writing-social-content/SKILL.md:1-190`

**Interfaces:**
- Consumes: the Task 1 test strings and the existing evidence-ledger, common-voice, and channel-reference contracts.
- Produces: a bundled persona authority and deterministic resolution workflow used before source locking.

- [ ] **Step 1: Create the bundled persona authority**

Create `references/personas.md` with these sections and rules:

```markdown
# 발신 페르소나

공개 페르소나 선택지는 정확히 두 개다. 모든 지원 채널은 두 페르소나 모두 사용할 수 있고, 오디언스는 글마다 별도로 정한다. 페르소나는 보이스가 아니라 어떤 문제와 증거를 중심에 놓을지 정하는 관점이다.

## 선택 규칙

1. 한 초안에는 주 페르소나를 정확히 하나만 둔다.
2. 사용자가 페르소나를 명시했으면 다시 묻지 않는다.
3. source가 한쪽을 명확히 가리키면 그 페르소나를 사용한다.
4. 선택에 따라 논지가 달라지는데도 모호하면 `FDE`와 `1인 빌더` 중 하나를 한 번만 묻는다.
5. 두 경험을 잇는 글도 주장과 독자를 소유하는 주 페르소나 하나를 먼저 고른다.

## FDE

- 중심 질문: 고객·조직의 어떤 문제를 어떤 성과와 지속 가능한 업무 변화로 바꿀 것인가.
- 다루는 근거: 문제 발견, 인터뷰, 설계, 구현, 검증, 채택, 운영 전환, 인수인계, AX 현장 관찰.
- 관점: 기술 도입보다 문제에서 성과까지의 책임 범위와 내가 떠난 뒤에도 남는 변화를 본다.
- 오디언스 후보: AX 의사결정자, 현장 실무자, 개발자, FDE·AI 엔지니어. 오디언스는 글마다 고르며 채널에 고정하지 않는다.
- 경계: 사용자나 source가 제공하지 않은 고객 장면, 성과, 고객·회사 식별정보, 내부 의사결정은 만들지 않는다.

## 1인 빌더

- 중심 질문: 내 가설을 무엇으로 만들고 어떻게 시장과 사용자에게 검증할 것인가.
- 다루는 근거: 문제 선택, 제품 결정, 직접 구현, 출시, 사용자 반응, 운영, 자동화, 수익 모델, 실패와 반복.
- 관점: 혼자 만든다는 사실보다 가설을 제품과 시장 증거로 바꾸는 전 과정을 본다.
- 오디언스 후보: 1인 창업가, 개발자 빌더, 비개발 프로덕트 메이커. 오디언스는 글마다 고르며 채널에 고정하지 않는다.
- 경계: 실제 근거가 있을 때만 출시, 사용자, 매출·수익, 사업 성과를 말한다. `솔로프리뉴어`, `1인 개발자`, `1인 창업가`는 문맥상 별칭이지 별도 페르소나가 아니다.

## 공통 기반과 제외

- AI Product Engineering, AX, 현장 우선, 직접 제작, 검증 우선은 두 페르소나의 공통 기반이다.
- AX Engineer는 공통 전문 영역을 설명하는 표현이며 세 번째 페르소나가 아니다.
- DA는 위시켓 내부 역할이며 이 스킬의 공개 페르소나 선택지에 넣지 않는다.
- 페르소나 선택은 source의 사실 권한을 넓히지 않는다.
```

- [ ] **Step 2: Load the persona reference before common voice**

Update `Reference loading contract` so startup order is:

```markdown
1. 시작할 때 `references/personas.md`를 읽고 발신 페르소나를 해결한다.
2. 시작할 때 `references/common-voice.md`를 읽는다.
3. 시작할 때 요청받은 채널 규칙 reference만 읽는다.
4. 근거 장부와 채널별 논지를 잠근 뒤, 요청 채널의 examples reference만 읽는다.
```

Renumber the remaining reference-loading rules without changing their meaning.

- [ ] **Step 3: Insert persona and audience resolution before source locking**

Add this workflow section before current step 1:

```markdown
### 0. 발신 페르소나와 오디언스 잠금

- `references/personas.md`를 읽고 `FDE` 또는 `1인 빌더` 중 주 페르소나를 정확히 하나 정한다.
- 사용자가 페르소나를 명시했으면 다시 묻지 않는다.
- source와 목적이 한 페르소나를 분명히 가리키면 그 선택을 사용한다.
- 선택이 논지를 실질적으로 바꾸는데도 모호할 때만 두 선택지를 한 번 묻는다. `DA`, `AX Engineer`, `혼합`을 추가 선택지로 만들지 않는다.
- 핵심 오디언스는 페르소나와 별도로 글마다 정하며 채널에 고정하지 않는다. source와 요청에서 명확하면 다시 묻지 않는다.
- 두 페르소나가 만나는 소재도 주장과 독자를 소유하는 주 페르소나 하나를 먼저 고른다.
```

- [ ] **Step 4: Apply persona framing to thesis lock and final review**

Add to `### 4. 채널별 논지 잠금`:

```markdown
- 선택한 페르소나의 중심 질문에서 출발하되, source가 뒷받침하지 않는 경험이나 성과를 추가하지 않는다.
```

Append these checks to `### 7. 검수`:

```markdown
8. 주 페르소나가 정확히 하나이며 논지·근거·오디언스가 그 관점과 일치하는가.
9. `DA`나 `AX Engineer`를 별도 공개 페르소나처럼 다루지 않았는가.
10. FDE 글의 고객·회사 맥락과 1인 빌더 글의 출시·사용자·수익 주장이 source 근거 안에 있는가.
```

- [ ] **Step 5: Add persona mistakes and boundaries**

Add rows to `Common Mistakes` for skipping persona resolution, binding persona to channel, blending two primary personas, and treating `DA` or `AX Engineer` as a third option. Add a boundary bullet saying persona choice frames supported content but never expands source authority.

- [ ] **Step 6: Run focused contracts**

Run:

```bash
python -m unittest tests.test_obsidian_content_flow_contracts.ObsidianContentFlowContractsTest
```

Expected: all tests in `ObsidianContentFlowContractsTest` pass.

- [ ] **Step 7: Commit the persona implementation**

```bash
git add \
  donggu-sns/skills/writing-social-content/SKILL.md \
  donggu-sns/skills/writing-social-content/references/personas.md
git commit -m "feat(sns): add author persona selection"
```

---

### Task 3: Document packaging and release version 2.7.6

**Files:**
- Modify: `donggu-sns/README.md:37-82`
- Modify: `donggu-sns/.claude-plugin/plugin.json:3`
- Modify: `donggu-sns/plugin.yaml:3`
- Modify: `.claude-plugin/marketplace.json:30`
- Modify: `tests/test_native_plugin_packages.py:109-116`

**Interfaces:**
- Consumes: the Task 2 bundled reference and workflow.
- Produces: discoverable package documentation and matching Claude, Hermes, and marketplace version `2.7.6`.

- [ ] **Step 1: Add persona routing to the README structure and flow**

Add `personas.md` to the reference tree and change the authoring flow to:

```text
사용자 source·URL·브리프
        ↓
FDE | 1인 빌더 페르소나 + 글별 오디언스 잠금
        ↓
common-voice + 요청 채널 규칙
        ↓
근거 장부 + 채널별 논지 잠금
        ↓
요청 채널의 번들된 문체 예시로 톤 캘리브레이션
        ↓
채널별 독립 초안
```

Add bullets stating that every supported channel works with both personas, audience is per draft, `DA` is not a public option, and persona selection never authorizes unsupported facts.

- [ ] **Step 2: Bump all donggu-sns package versions to 2.7.6**

Replace `2.7.5` with `2.7.6` in:

```text
donggu-sns/.claude-plugin/plugin.json
donggu-sns/plugin.yaml
.claude-plugin/marketplace.json
tests/test_native_plugin_packages.py
```

- [ ] **Step 3: Run version and full repository tests**

Run:

```bash
python -m unittest \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_claude_marketplace_versions_match_dual_harness_packages \
  tests.test_native_plugin_packages.NativePluginPackageTests.test_sns_claude_and_hermes_manifests_share_identity_and_version
python -m unittest discover -s tests -p 'test_*.py'
git diff --check
```

Expected: both version tests pass, the full suite passes, and `git diff --check` emits no output.

- [ ] **Step 4: Commit documentation and release metadata**

```bash
git add \
  donggu-sns/README.md \
  donggu-sns/.claude-plugin/plugin.json \
  donggu-sns/plugin.yaml \
  .claude-plugin/marketplace.json \
  tests/test_native_plugin_packages.py
git commit -m "chore(sns): release persona routing 2.7.6"
```

---

### Task 4: Validate the skill behavior and installed package

**Files:**
- Verify: `donggu-sns/skills/writing-social-content/SKILL.md`
- Verify: `donggu-sns/skills/writing-social-content/references/personas.md`
- Verify: installed Claude plugin cache for `donggu-sns` version `2.7.6`

**Interfaces:**
- Consumes: committed source package version `2.7.6`.
- Produces: behavioral evidence for explicit FDE selection, explicit 1인 빌더 selection, ambiguous selection, channel independence, and installed-package parity.

- [ ] **Step 1: Run skill-specific behavioral scenarios**

Use the `superpowers:writing-skills` testing protocol with fresh agents for these prompts:

```text
FDE 관점으로 이 브리프를 LinkedIn 글로 써줘: 고객이 데모 이후 운영 인수에 실패했다.
```

Expected: selects FDE without asking again and does not invent a customer or outcome.

```text
1인 빌더 관점으로 이 브리프를 Maily 글로 써줘: 혼자 만든 제품의 첫 배포에서 운영 체크리스트가 빠졌다.
```

Expected: selects 1인 빌더 without asking again; Maily remains supported; no unsupported launch, user, or revenue claim appears.

```text
이 메모로 Blog 글을 써줘: 직접 만든 자동화가 일주일 뒤에도 계속 쓰였다.
```

Expected: asks only whether the primary persona is `FDE` or `1인 빌더` when the source does not identify whose workflow it was.

```text
FDE 경험을 내 제품에 적용한 이야기로 Threads 글을 써줘.
```

Expected: resolves one primary persona, treats the other as supporting context, and does not create a hybrid option.

- [ ] **Step 2: Refresh the installed Claude plugin**

Run:

```bash
claude plugin update donggu-sns@donggu-skills --scope user
```

Expected: Claude reports `donggu-sns@donggu-skills` updated to `2.7.6` and notes that restart is required. Do not edit generated cache files by hand.

- [ ] **Step 3: Verify installed source parity**

Locate the installed `donggu-sns` cache version and verify:

```text
version = 2.7.6
SKILL.md contains references/personas.md
references/personas.md matches the source repository file
```

- [ ] **Step 4: Run final evidence checks**

Run:

```bash
python -m unittest discover -s tests -p 'test_*.py'
git status --short --branch
git log -4 --oneline --decorate
```

Expected: full suite passes; the worktree has no uncommitted implementation changes; the latest commits include the design, contract, feature, and release changes.

- [ ] **Step 5: Report completion**

Report changed files, persona behavior, version `2.7.6`, test counts, installed-cache parity, and any behavioral scenario that could not be executed.
