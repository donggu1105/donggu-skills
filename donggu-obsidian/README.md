# donggu-obsidian

> Obsidian PKM vault operations skill collection — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-6-green)](#-skills)
[![Compatible](https://img.shields.io/badge/PKM-LYT%20%7C%20PARA%20%7C%20Zettelkasten-blue)](#-사용-가정)

LYT / PARA / Zettelkasten 스타일 PKM vault 운영의 정기 의례 자동화. **콘텐츠 파이프라인** (저널 → CORE → Channel Pack → CASE)을 운영하는 PKM 사용자용.

---

## 📚 Skills

| Skill | 호출 | 사용 시점 | Output |
|---|---|---|---|
| **checking-vault-health** | `donggu-obsidian:checking-vault-health` | 월 1회 시스템 회고, 주말 추출 직전 | 4 layer 보고서 (P0-P4 + 긍정 신호 + 한 줄 요약) |
| **core-review-approval** | `donggu-obsidian:core-review-approval` | 검토된 CORE 후보 적용 시 | native preview/apply 및 복구 |
| **decompose-canon** | `donggu-obsidian:decompose-canon` | 명시적으로 선택한 canon 분해 시 | atomic 후보와 검토 handoff |
| **extract-core** | `donggu-obsidian:extract-core` | 주말 1회 (저널 5-7건 누적 후) | atomic claim 후보 3-5개 (점수 + 채택 권장) |
| **finding-duplicate-notes** | `donggu-obsidian:finding-duplicate-notes` | 월 1회 또는 atomic 의심 노트 발견 시 | 5 패턴 중복 발견 + 조치 추천 |
| **life-os** | `/donggu-obsidian:life-os` | Daily 체크인, 빠른 Capture, 첨부 기록 시 | 질문별 즉시 저장된 Daily 기록 |

---

## 🌙 Life OS 설치와 연결

Hermes에는 repository subdirectory plugin을 설치한다.

```bash
hermes plugins install --force --enable donggu1105/donggu-skills/donggu-obsidian
```

대상 Vault와 private lock-state 경로를 로컬 환경에만 설정한다.

| 환경 키 | 값 |
|---|---|
| `DONGGU_LIFE_OS_VAULT_ROOT` | `Life OS/`를 포함한 절대 Vault root |
| `DONGGU_LIFE_OS_STATE_ROOT` | Vault 밖의 mode `0700` private state directory; 기본값은 `$XDG_STATE_HOME/donggu-life-os` 또는 `~/.local/state/donggu-life-os` |
| `DONGGU_LIFE_OS_TIMEZONE` | `Asia/Seoul` (기본값) |

실제 Discord ID는 공개 저장소에 넣지 말고 Hermes 로컬 설정에서만 바인딩한다.
Life OS 답변 원문은 `pre_gateway_dispatch`에서 Discord 준비·첨부 주입 전에 짧게 보관하며, native record handler는 정확히 일치하는 Hermes 세션 컨텍스트와 DB 행 ID만 결합한다. SessionDB의 준비된 `content`는 답변으로 사용하지 않는다.

```yaml
discord:
  free_response_channels:
    - "<life-os-channel-id>"
  channel_skill_bindings:
    - id: "<life-os-channel-id>"
      skill: donggu-obsidian:life-os
  channel_prompts:
    "<life-os-channel-id>": >-
      Use only the donggu-obsidian:life-os skill and its native tools in this
      channel. Never use generic filesystem tools as fallback, and never expose
      internal paths, credentials, IDs, or tool state.
```

기존 `discord` 설정을 통째로 교체하지 않는다. 기존 global `require_mention` 값은 보존하고,
`free_response_channels`와 기존 `channel_skill_bindings`에는 Life OS 채널 항목만 합집합으로
추가한다. `allowed_channels`가 없으면 계속 생략하고, 이미 있으면 기존 항목을 보존한 채
`<life-os-channel-id>`만 추가한다. 설정 후 `hermes config check`로 검증한다.

Hermes plugin skill은 일반 `hermes skills list`나 system prompt 인덱스에 노출되지 않는다.
`ctx.register_skill()`로 등록된 정규 이름 `donggu-obsidian:life-os`를 명시 로드하며,
진단할 때는 `skill_view("donggu-obsidian:life-os")` 결과의 `success`를 확인한다.

22시 체크인은 `Asia/Seoul` 기준 cron `0 22 * * *`으로 `donggu-obsidian:life-os` skill과 `donggu_life_os_start_daily`를 호출한다. 기존 active 상태를 초기화하거나 두 번째 reminder를 만들지 않고, pending question 또는 이미 완료됐다는 결과만 전달한다.

아래 recipe는 대상 Vault root에서 실행한다. placeholder를 로컬 값으로 바꾸고, 기존 exact-name
job이 있으면 그 ID를 `LIFE_OS_CRON_JOB_ID`에 넣는다. 없으면 create 출력의 `Created job:` 뒤
12자리 ID를 한 번 캡처한다. 이후 edit, readback, run, history 모두 같은 ID만 사용한다.

```bash
LIFE_OS_VAULT_ROOT="$(pwd)"
LIFE_OS_CHANNEL_ID="<life-os-channel-id>"
LIFE_OS_CRON_NAME='Life OS 데일리 체크인 (22:00)'
LIFE_OS_CRON_PROMPT='Use the donggu-obsidian:life-os skill. Call donggu_life_os_start_daily for the current KST date. Return only its pending question; if completed, return 오늘 Daily 기록은 이미 완료됐어요.'

life_os_cron_ids() {
  python3 -c '
import re, sys
name = sys.argv[1]
current = None
for raw in sys.stdin:
    line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw.rstrip("\n"))
    job = re.match(r"\s*([0-9a-f]{12})\b", line)
    if job:
        current = job.group(1)
    named = re.match(r"\s*Name:\s+(.*)$", line)
    if named and named.group(1) == name and current:
        print(current)
' "$LIFE_OS_CRON_NAME"
}

LIFE_OS_CRON_LIST="$(hermes cron list --all)"
LIFE_OS_CRON_IDS="$(printf '%s\n' "$LIFE_OS_CRON_LIST" | life_os_cron_ids)"
LIFE_OS_CRON_MATCH_COUNT="$(printf '%s\n' "$LIFE_OS_CRON_IDS" | sed '/^$/d' | wc -l | tr -d ' ')"

case "$LIFE_OS_CRON_MATCH_COUNT" in
  0)
    LIFE_OS_CRON_CREATE="$(hermes cron create '0 22 * * *' "$LIFE_OS_CRON_PROMPT" \
      --name "$LIFE_OS_CRON_NAME" \
      --deliver "discord:${LIFE_OS_CHANNEL_ID}" \
      --skill donggu-obsidian:life-os \
      --workdir "$LIFE_OS_VAULT_ROOT")"
    LIFE_OS_CRON_JOB_ID="$(printf '%s\n' "$LIFE_OS_CRON_CREATE" | \
      sed -nE 's/.*Created job:[[:space:]]*([0-9a-f]{12}).*/\1/p')"
    ;;
  1) LIFE_OS_CRON_JOB_ID="$LIFE_OS_CRON_IDS" ;;
  *) echo 'expected zero or one exact-name cron job' >&2; exit 1 ;;
esac
case "$LIFE_OS_CRON_JOB_ID" in ''|*[!0-9a-f]*) exit 1 ;; esac

# create 직후 또는 기존 job 조정 시 동일 ID를 idempotent하게 정규화한다.
hermes cron edit "$LIFE_OS_CRON_JOB_ID" \
  --schedule '0 22 * * *' \
  --prompt "$LIFE_OS_CRON_PROMPT" \
  --name "$LIFE_OS_CRON_NAME" \
  --deliver "discord:${LIFE_OS_CHANNEL_ID}" \
  --skill donggu-obsidian:life-os \
  --workdir "$LIFE_OS_VAULT_ROOT"

LIFE_OS_CRON_LIST="$(hermes cron list --all)"
LIFE_OS_CRON_READBACK_IDS="$(printf '%s\n' "$LIFE_OS_CRON_LIST" | life_os_cron_ids)"
if [ "$LIFE_OS_CRON_READBACK_IDS" != "$LIFE_OS_CRON_JOB_ID" ]; then
  echo 'cron readback did not match the captured job ID' >&2
  exit 1
fi
hermes cron run "$LIFE_OS_CRON_JOB_ID"
hermes cron runs "$LIFE_OS_CRON_JOB_ID" --limit 5
```

`hermes config get timezone --json`의 readback이 `Asia/Seoul`인지 확인하고, cron list readback에서
exact name이 캡처한 ID로 정확히 한 번 나타나지 않으면 run하지 않는다.

Claude Code에서는 `/donggu-obsidian:life-os`를 호출한다. Codex에서는 같은 skill directory를 `~/.codex/skills/life-os` 공유 링크로 연결한다.

```bash
LIFE_OS_SKILL_SOURCE="$(pwd)/donggu-obsidian/skills/life-os"
LIFE_OS_CODEX_SKILLS="$(python3 -c 'from pathlib import Path; print(Path.home() / ".codex/skills")')"
ln -s "$LIFE_OS_SKILL_SOURCE" "$LIFE_OS_CODEX_SKILLS/life-os"
```

수동 진단이나 Hermes 외 실행에는 shared runtime CLI를 사용한다. `status`, `start`, `record`는 stdout에 JSON을 출력하고 오류는 stderr와 exit code 2로 반환한다.

```bash
python3 donggu-obsidian/skills/life-os/scripts/life-os.py \
  --vault-root "$DONGGU_LIFE_OS_VAULT_ROOT" status
```

첨부는 임시 cache path나 URL을 노트에 남기지 않는다. runtime이 실제 파일을 flat Vault layout에 저장하고 Daily 또는 Capture에서 직접 링크한다.

```text
Life OS/Attachments/
├── A001 - readable-name.ext
└── A002 - another-file.ext
```

### 수동 복구

runtime이 temporary/manual recovery 오류를 반환하면 쓰기를 멈추고 `.<note>.life-os-*`,
`.life-os-attachment-*`, `.life-os-recovery-*` 파일과
`DONGGU_LIFE_OS_STATE_ROOT`의 Vault별 `note-archives/` 아래
`.life-os-note-stage-*`, `.life-os-note-archive-*`, `.life-os-note-aborted-*`를 먼저
byte-for-byte 보존한다. 기존 노트 갱신은 state archive와 Vault가 같은 filesystem에
있고 atomic exchange를 지원할 때만 실행되며, 교체된 canonical은 private archive에
누적된다. pending stage가 남으면 이후 갱신은 수동 복구 전까지 중단된다. 복구 파일을
canonical 파일 및 원본과 크기·SHA-256으로 비교하고, symlink는 대상을 따라가지 말고
링크 자체와 대상을 따로 확인한다. 비교와 별도 백업이 끝나기 전에는 어떤 residual이나
archive도 삭제하지 않는다. 명시적인 verified GC 또는 수동 검증 후에만 정리한다.

---

## 🔁 Skill Chain 흐름

```
                 ┌────────────────────────┐
                 │  checking-vault-health │  (월 1회 시스템 점검)
                 └────────────┬───────────┘
                              │
                ┌─────────────┼──────────────┐
                ▼                            ▼
       absorbed callout 발견           extracted_to: [] 5+건
                │                            │
                ▼                            ▼
   ┌───────────────────────┐    ┌────────────────────────┐
   │ finding-duplicate-    │    │     extract-core       │  (주말 추출 의례)
   │       notes           │    └───────────┬────────────┘
   └───────────────────────┘                │
                ▲                            │
                │     채택 시 기존 CORE      │
                └────────── 중복 검사 ──────┘
```

각 skill의 `## 관련 Skill` 섹션이 자동 chain 권장.

---

## 🧬 Skill 상세

### 🩺 `checking-vault-health`

PKM vault의 **콘텐츠 파이프라인 4 layer** (입구·정제·출구·큐레이션) 흐름 점검. broken link audit 아님.

**점검 카테고리 5종**:
1. 입구 단절 (저널·캡처 0건 7일+) — **P0**
2. 파이프라인 정체 (추출·인용 안 됨 1주+) — **P1**
3. 가이드 안티 패턴 (Channel Pack에 본문 직접 작성 등) — **P1**
4. broken wikilink (콤마·공백 typo) — **P2**
5. stub 적체 + MOC 임계 미달 — **P3**

**보고서 형식**: P0-P4 (발견·영향·조치 3줄) + 긍정 신호 1-3개 + 한 줄 요약.

### 💎 `extract-core`

빌드 저널의 "💎 추출 후보" 섹션을 atomic CORE로 승격하는 주말 의례.

**Atomic 평가 5 기준** (각 2점, 총 10점):
- 1 idea = 1 note (1개 아이디어만?)
- "X는 Y다" 문장형 (완성된 주장?)
- 본인 voice (객관 정리 아님?)
- 기존 CORE 중복 X (vault search)
- 시간 좌표 없음 (영구 자산?)

**채택 후 자동 작업**:
- 새 CORE 노트 생성 (`TPL - Core` 컨벤션 매칭)
- 저널 frontmatter `extracted_to: [[CORE - X]]` 자동 link

### 🔍 `finding-duplicate-notes`

vault의 1 idea = 1 note 위반 발굴. 5 패턴 audit:

| 패턴 | 신호 | 조치 |
|---|---|---|
| **Semantic duplicates** | 다른 제목, 같은 핵심 주장 | merge 권장 — 하나로 통합 + alias 보존 |
| **Naming twins** | 거의 같은 제목 (콤마·공백 차이) | 1개 채택, 다른 거 redirect |
| **Absorbed-not-merged** | "흡수됨" callout 또는 `evolves_from` frontmatter 있지만 본문 살아있음 | 의도 보존이면 OK, 아니면 archive |
| **Snippet twins** | 같은 Hook/Lesson 2+ 노트 분산 | 변형 의도면 보존, 아니면 1개 채택 |
| **Source redundancy** | 같은 외부 자료 2+ SOURCE | 합병 + 인용 일괄 fix |

**자동 merge 절대 X** — 미세 차이가 본인 의도일 수 있음 (snippet A/B 변형 등).

---

## 🎯 사용 가정

- **PKM 시스템**: LYT (Linking Your Thinking) / PARA / Zettelkasten / Second Brain
- **frontmatter `type` enum** 컨벤션 (예: `core | source | case | snippet | project | moc | foundation | journal`)
- **`extracted_to:` 또는 비슷한 추출 추적 키** 사용 (skill이 추출 자동 link)
- **본문 callout 또는 `evolves_from` frontmatter**로 노트 evolution 추적

> 다른 vault 적용 시 각 skill의 `## Vault-Specific Context` 섹션 참조하여 path/key 매핑 조정.

---

## 💡 활용 시나리오

### 주말 의례 (매주 토·일, 30-60분)

```
1. /donggu-obsidian:checking-vault-health
   → 시스템 흐름 점검, 정체 layer 식별

2. /donggu-obsidian:extract-core
   → 그 주 저널 → atomic CORE 후보 3-5개 → 1-3개 채택

3. (1 결과에 중복 신호 있으면) /donggu-obsidian:finding-duplicate-notes
   → 5 패턴 audit → 조치 추천
```

### 월간 retro (월말, 1시간)

```
1. /donggu-obsidian:checking-vault-health   (전월 vault 진화 확인)
2. /donggu-obsidian:finding-duplicate-notes (월 1회 중복 audit)
3. (skill 결과 기반) Pattern 발굴·MOC 보강·강의 자산 정리
```

### 분기 (강의·B2B 자산 정리 직전)

```
1. /donggu-obsidian:finding-duplicate-notes  (중복 정리 → 모듈 조립 가능)
2. (사용자 직접) 누적된 CORE/Foundation/Case로 Teaching Module 조립
```

---

## 🔗 관련

- [donggu-skills marketplace](../) — 본 plugin 부모
- [Claude Code Plugin Spec](https://claude.com/claude-code) — plugin/marketplace 작동 방식
- [superpowers:writing-skills](https://github.com/obra/superpowers) — skill 작성 가이드 (RED-GREEN-REFACTOR)

---

## 📜 License

[MIT](../LICENSE) © 2026 강동현 (donggu)
