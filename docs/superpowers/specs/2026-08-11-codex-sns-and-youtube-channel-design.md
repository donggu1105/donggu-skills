# Codex용 donggu-sns와 YouTube 채널 정본 설계

## 목표

`donggu-skills`가 기존 도메인별 plugin 경계를 유지한 채 Codex marketplace를 수용하도록 만들고, 첫 Codex 설치 가능 plugin으로 `donggu-sns`를 제공한다. 같은 변경 묶음에서 개인 브랜딩 볼트의 YouTube 운영 정본에 공개 채널 `https://www.youtube.com/@donggu_ai`를 기록한다.

## 성공 조건

- Codex가 `donggu-skills` marketplace에서 `donggu-sns`를 발견하고 설치할 수 있다.
- 설치된 `donggu-sns`는 기존 `skills/` 트리를 그대로 읽으며, 별도 복사본을 만들지 않는다.
- `writing-social-content`의 공개 페르소나는 계속 `FDE`와 `1인 빌더` 두 개뿐이다.
- `DA`는 위시켓 내부 역할로 남고, `AX Engineer`는 공통 전문 영역일 뿐 세 번째 페르소나가 아니다.
- Claude, Hermes, Codex용 `donggu-sns` 버전이 `2.7.7`로 일치한다.
- Obsidian의 `INDEX - YouTube.md`에서 `@donggu_ai` 공개 채널을 찾을 수 있다.
- 두 저장소의 기존 사용자 변경을 덮어쓰거나 함께 커밋하지 않는다.

## 범위

### 포함

1. `donggu-skills` 저장소에 repo-local Codex marketplace catalog를 추가한다.
2. catalog에는 이번 릴리스에서 유효한 `donggu-sns` entry 하나만 등록한다.
3. `donggu-sns`에 Codex manifest를 추가하고 기존 일곱 개 skill을 `./skills/`에서 노출한다.
4. Claude marketplace, Claude plugin manifest, Hermes manifest, Codex manifest와 Codex marketplace의 버전을 `2.7.7`로 맞춘다.
5. README에 Codex 설치와 새 thread에서의 확인 절차를 추가한다.
6. manifest, marketplace, skill 노출, 버전 일치에 대한 계약 테스트를 추가한다.
7. 볼트의 YouTube 운영 정본에 공개 채널 링크를 추가한다.

### 제외

- `donggu-obsidian`, `donggu-docs`, `donggu-media`, `donggu-apply`를 이번에 Codex 설치 가능 상태로 만들지 않는다.
- 기존 plugin 디렉터리를 `plugins/` 아래로 이동하거나 복제하지 않는다.
- `~/.codex/skills`에 skill 파일을 직접 복사하지 않는다.
- 새로운 SNS 통합 router나 skill registry를 만들지 않는다. 일곱 개 skill의 현재 경계와 frontmatter trigger를 유지한다.
- 페르소나 선택 규칙이나 채널별 글쓰기 동작을 변경하지 않는다.
- YouTube 채널 URL을 개별 영상의 `youtube_url` 필드나 템플릿에 넣지 않는다.
- 현재 사용자 변경이 있는 `INDEX - Channels.md`와 `VOICE - YouTube.md`는 수정하지 않는다.

## 구조

### donggu-skills marketplace

repo-local catalog의 정본은 `.agents/plugins/marketplace.json`이다. marketplace 이름은 `donggu-skills`, 표시명은 `Donggu Skills`로 한다. 기존 저장소가 plugin들을 루트의 `donggu-<domain>/`에 보관하므로 `donggu-sns` entry는 `./donggu-sns`를 가리킨다. 이 catalog는 향후 다른 domain plugin을 append할 수 있지만, 존재하지 않는 Codex manifest를 가진 plugin은 미리 등록하지 않는다.

### donggu-sns Codex plugin

`donggu-sns/.codex-plugin/plugin.json`은 기존 plugin과 같은 `donggu-sns` 식별자를 사용하고 `skills: "./skills/"`를 선언한다. 설치 화면 metadata에는 현재 경계를 반영한다.

- 글: `writing-social-content`
- 영상 기획: `youtube`
- 산출물: `make-insta-card-news`, `make-shorts`, `get-stock-image`, `get-ai-image`
- 발행: `publish-sns`

Codex용 별도 skill 본문은 만들지 않는다. Claude와 Codex가 동일한 `SKILL.md` 파일을 읽게 하여 페르소나, 오디언스, 근거, 게시 승인 규칙이 한 곳에서 진화하도록 한다.

### Obsidian YouTube 채널 정본

`Personal Branding/40_Channel_Packs/YouTube/INDEX - YouTube.md`에 다음 채널 계정 섹션을 추가한다.

```markdown
## 채널 계정

- 공개 채널: [@donggu_ai](https://www.youtube.com/@donggu_ai)
```

이 노트는 YouTube 제작 라인의 운영 정본이므로 채널 계정 링크도 여기에서 한 번만 소유한다. 개별 영상 URL과 채널 URL을 구분하고 파생 문서에 중복 저장하지 않는다. 노트의 `updated` 값은 `2026-08-11`로 갱신한다.

## 작업 격리와 통합

- `donggu-skills`: `.worktrees/codex-donggu-sns`와 `feat/codex-donggu-sns`를 사용한다.
- Obsidian 볼트: `.worktrees/youtube-channel-link`와 `feat/youtube-channel-link`를 사용한다.
- 각 worktree는 생성 직후 baseline 검증을 실행한다.
- 구현은 저장소별로 범위가 분리된 Codex native executor에게 맡긴다.
- 각 branch는 독립적으로 검토하고 검증한 뒤 원래 저장소에 통합한다.
- 볼트 main은 사용자 변경이 많으므로 target 파일이 여전히 clean인지 통합 직전에 다시 확인한다. target 파일에 새 사용자 변경이 생기면 자동 통합을 중단하고 branch 결과만 보존한다.

## 오류와 안전 경계

- 잘못된 marketplace entry 하나가 전체 catalog를 흐리지 않도록 Codex manifest가 존재하는 `donggu-sns`만 등록한다.
- manifest 경로는 plugin root 내부 상대 경로만 사용한다.
- marketplace 추가와 plugin 설치는 로컬 Codex 상태만 바꾸며, 실패하면 저장소 변경과 설치 상태를 구분해 보고한다.
- 외부 채널 게시, YouTube API 호출, 계정 인증은 수행하지 않는다.
- iCloud 볼트의 unrelated dirty files는 stash, reset, checkout, add 또는 commit하지 않는다.
- 기존 Claude와 Hermes 배포 파일은 삭제하지 않고 버전만 동기화한다.

## 테스트와 검증

### donggu-skills

계약 테스트는 다음을 증명해야 한다.

1. `.agents/plugins/marketplace.json`이 유효한 JSON이고 marketplace 이름이 `donggu-skills`다.
2. catalog에는 `donggu-sns`만 있으며 source가 기존 plugin 디렉터리를 가리킨다.
3. `donggu-sns/.codex-plugin/plugin.json`이 유효하고 `skills`가 `./skills/`다.
4. Codex manifest가 노출하는 디렉터리에 현재 일곱 개 `SKILL.md`가 모두 존재한다.
5. Claude marketplace, Claude manifest, Hermes manifest, Codex manifest와 Codex marketplace가 모두 `2.7.7`이다.
6. 기존 페르소나 계약 테스트와 전체 Python test suite가 통과한다.
7. Codex plugin validator와 `git diff --check`가 통과한다.
8. 로컬 marketplace 추가 후 Codex가 `donggu-sns`를 발견하고 설치된 plugin의 skill 목록을 표시한다.

### Obsidian 볼트

1. 정본 노트에 정확한 URL이 한 번 존재한다.
2. 채널 URL이 `TPL - Video Build`나 개별 `youtube_url` 필드에 추가되지 않는다.
3. frontmatter와 Obsidian Markdown 구조가 유지된다.
4. `git diff --check`가 통과하고 branch diff에는 정본 노트만 포함된다.

## 완료 상태

두 branch가 검토·통합되고, main 기준 검증과 Codex의 실제 발견·설치 확인이 끝나면 완료다. Codex는 설치 후 새 thread에서 plugin skill 목록을 다시 로드해야 하므로 최종 안내에 그 경계를 명시한다.
