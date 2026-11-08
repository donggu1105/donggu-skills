# Vault Voice

동구 보이스의 정본은 Obsidian 볼트에 있다. 이 문서는 작성 전에 그 정본을 찾아 읽는 절차만 정한다. 보이스 내용 자체는 여기 적지 않는다.

## 볼트 찾기

1. `$OBSIDIAN_VAULT_PATH`가 있으면 그 경로를 쓴다.
2. 없으면 `~/Library/Application Support/obsidian/obsidian.json`에서 `open: true`인 볼트의 `path`를 쓴다 (현재 `.../iCloud~md~obsidian/Documents/ontology`).
3. 볼트를 찾지 못하거나 아래 필수 파일이 없으면 작성을 멈추고 사용자에게 알린다. 다른 문서나 기억으로 보이스를 대신 채우지 않는다.
4. iCloud 파일이 비어 읽히면(dataless) `brctl download <file>` 후 다시 읽는다.

## 시작할 때 읽는 파일 (필수)

| 순서 | 파일 | 소유하는 것 |
|---|---|---|
| 1 | `Personal Branding/05_Brand/VOICE - 공통.md` | 공통 태도·문장·주장 방식·사실 경계·금지 표현·마무리 |
| 2 | `Personal Branding/40_Channel_Packs/<채널>/_anchors/VOICE - <채널>.md` | 채널 톤·채널 금지·`canon:` 정전 목록 |

채널 폴더: Blog → `Blog`, LinkedIn → `LinkedIn`, Threads → `Threads`, Maily → `Maily`.

- 두 파일이 충돌하면 사실 경계·금지 표현은 `VOICE - 공통`, 채널 톤은 채널 앵커를 따른다.
- 분량·출력 형식·해시태그 개수·검수 항목은 이 스킬의 채널 reference가 정본이다. 앵커에 같은 항목이 있어도 스킬 reference를 따른다.
- 앵커의 `## 실측` 절은 참고 기록이다. 규칙이 아니다.
- 앵커의 `## 채널 운영 메모`(발행 시간·알고리즘·미디어)는 작성에 쓰지 않는다.

## 논지를 잠근 뒤 읽는 파일 (톤 캘리브레이션)

- 채널 앵커 frontmatter `canon:`에 있는 위키링크를 같은 채널 폴더에서 찾아 연다. `[[LinkedIn - 그 뒤를 메우는 사람]]` → `Personal Branding/40_Channel_Packs/LinkedIn/LinkedIn - 그 뒤를 메우는 사람.md`.
- 발행 본문 구획만 읽는다: `## Draft` · `## 발행` · `## 본문` · `# 발행 원고`. `## 부품` · `## 메모` · `## 연결` · `## 편집 메모` · frontmatter는 읽지 않는다.
- 같은 장르(평서 에세이 / 존댓 후기)의 정전을 우선한다. 장르는 정전 노트의 `register:` 또는 본문 종결로 판단한다.
- `canon: []`이거나 정전 파일이 없으면 캘리브레이션을 건너뛰고 앵커 톤 규칙만 적용한다.
- 정전 외의 과거 글, 같은 폴더의 다른 원고, `20_Core` 등은 자동으로 열지 않는다.

## 정전을 읽을 때의 경계

- 정전에서는 register·문장 길이·문단 호흡·후크 밀도·전환·종결 방식만 추출한다.
- 정전의 사실·숫자·사례·비유·결론·고유 표현·펀치라인은 현재 글에 가져오지 않는다. 근거가 아니다.
- 현재 source에서 확인되지 않은 관점과 1인칭 경험을 정전에서 빌려오지 않는다.
