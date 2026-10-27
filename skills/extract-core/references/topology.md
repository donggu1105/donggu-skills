# PB 토폴로지 — CORE가 놓이는 자리

정본은 볼트 `Personal Branding/_GUIDES/RULES.md`(폴더 지도·프리픽스·최소 frontmatter)다. 이 파일은 그 구조 위에서 CORE를 어디에 어떻게 잇는지만 정한다. RULES.md와 다르면 RULES.md가 이긴다. 작업 전에 RULES.md를 다시 읽고 폴더 이름이 바뀌었으면 실물을 따른다.

## 노드

| 노드 | 집 | 역할 | voice |
|---|---|---|---|
| `SOURCE - <저자-제목>` | `10_Sources` | 외부 자료 1:1 인덱스 | 자료 정리 톤 |
| `FOUND - …` | `30_Foundations` | 객관 구조. SOURCE 1개 이상 인용 | 본인 voice 금지 |
| `CORE - <X는 Y다>` | `20_Core` | 동구의 원자 POV. 1 idea = 1 note | 동구 voice |
| `CASE - …` | `80_Cases` | 경험 회고 (SAR) | 동구 voice |
| `<채널> - <제목>` | `40_Channel_Packs/<채널>` | 출고한 글 | 채널 voice |
| `MOC - …` | `50_MOCs/Topics` | 주제 인덱스 | — |
| `PROJECT - …` | `Portfolio` | 경력·제품 카드 | — |
| 강의 부품 | `60_Projects/Teaching` | 재사용 Hook·Closing 등 | — |
| `관찰 - …`, `CAPTURE - …` | `00_Inbox` | 입구 | — |

## 엣지 (CORE 기준)

```text
SOURCE ──인용──▶ FOUND ──"결론 POV는 CORE가 소유"──▶ CORE
SOURCE ─────────────────근거───────────────────────▶ CORE
CASE ───────────────────증거───────────────────────▶ CORE
관찰(00_Inbox) ─────────최초 관찰──────────────────▶ CORE
CORE ──출고──▶ Channel Pack (LinkedIn → Blog/Threads/Maily 파생)
CORE ◀──Related──▶ CORE
MOC(Topics) ──💡 Core 섹션──▶ CORE
PROJECT ──원칙──▶ CORE   (사용자가 요청할 때만 연결)
```

- 사실은 SOURCE·FOUND·CASE가 갖고, 해석은 CORE가 갖는다. CORE에 외부 사실을 길게 옮기지 않고 SOURCE/FOUND로 링크한다.
- FOUND가 이미 같은 구조를 설명하면 CORE는 그 FOUND를 `객관 구조:`로 링크하고 결론만 소유한다.

## CORE의 `## 근거와 연결` (현재 형식)

CORE 하단 연결 섹션. 있는 줄만 쓴다. 섹션 이름은 기존 노트가 `## 📂 연결된 콘텐츠`·`## 📂 연결`이면 그 이름을 유지하고, 새 노트는 `## 근거와 연결`로 쓴다.

```markdown
## 근거와 연결

- 객관 구조: [[FOUND - …]]
- 출처: [[SOURCE - …]]
- 경험: [[CASE - …]]
- 최초 관찰: [[관찰 - …]]
- 출고: [[LinkedIn - …]] · [[Blog - …]] · [[Threads - …]]
- 관련: [[CORE - …]] — 관계 한 줄
- MOC: [[MOC - …]] · [[MOC - …]]
```

## 역방향 배선 (CORE를 만들거나 연결할 때 같은 턴에)

| 대상 | 어디에 | 무엇을 |
|---|---|---|
| 원천 채널 노트 + 같은 주제 파생 채널 노트 | 본문 `## 연결` (없으면 `## 편집 메모` 위에 생성) | `- CORE: [[CORE - …]]` |
| 관련 CORE | 그 노트의 연결 섹션 `관련:`/`인접 Core:` 줄 | 새 CORE 추가 (양방향) |
| 근거로 쓴 SOURCE·FOUND·CASE | 그 노트의 `## 연결`/`## 관련 CORE` | 새 CORE 추가 |
| MOC | `## 💡 Core (원칙/인사이트)` (FDE MOC는 `💡 소울 Core` 또는 맞는 주제 섹션) | `- [[CORE - …]] — 한 줄` |

- MOC는 1~2개만. CORE `topics`와 MOC `topics`/주제가 겹치는 곳을 고른다. 주요 MOC: FDE(`MOC - Forward Deployed Engineer`), AX(`MOC - AX Bridge`), Product Engineer, AI Product Engineering, 1인 빌더, 고객집착, 협업과 설득, 커리어 전환.
- MOC에 맞는 섹션이 없을 때만 섹션 하나를 추가한다. 새 MOC 파일은 만들지 않는다 (RULES: 같은 주제 5+ 모이면 사용자가 판단).
- MOC의 `📊 콘텐츠 현황` 숫자는 고치지 않는다 (손으로 관리되는 값이고 이미 어긋나 있다).
- 링크는 실제 파일 제목과 정확히 맞춘다. 쓰기 전 대상 파일이 있는지 확인한다. 없는 노트로의 링크는 만들지 않는다.

## 레거시 (지우지 않고, 새로 만들지 않는다)

- 채널 노트 frontmatter `core_principle`·`core_connection`, `## 부품` 표: 이미 있으면 같은 링크로 갱신만.
- CORE frontmatter `persona`·`pillar`·`audience`·`channels`·`tone`·`title`: 새 CORE에 쓰지 않는다.
- `✂️ Snippets`·`HOOK -` 노트: 현재 만들지 않는다. 재사용 한 줄은 CORE `## 💬 자주 쓰는 표현`에 둔다.
