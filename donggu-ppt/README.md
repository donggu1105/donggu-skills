# donggu-ppt

> Presentation decks — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-1-green)](#skills)

발표 자료·덱·장표·PPT·슬라이드 요청을 **단일 HTML 파일** 하나로 만든다. 검증된 스타일 계약(큰 타이포 스케일·모션 문법·색 역할 토큰)과 부품 전시장이 고정 출력이라, 어떤 레퍼런스를 가져와도 결과는 '내 덱' 스타일로 나온다.

## Skills

| Skill | 호출 | 용도 | Output |
|---|---|---|---|
| **donggu-deck** | `donggu-ppt:donggu-deck` | 내러티브 합의 → `template.html` 복사 → `components.html` 부품으로 장 조립 → 라운드마다 같은 파일 갱신 | `index.html` + `assets/` (오프라인에서 열림) |

## 정본 셋

- `skills/donggu-deck/SKILL.md` — 절차와 취향(실제 피드백에서 증류한 선호 규칙, 근거 병기)
- `skills/donggu-deck/references/tokens.md` — 수치 계약(타이포 스케일·모션·색 역할)
- `skills/donggu-deck/template.html` + `components.html` — 계약이 박힌 실물과 부품 카탈로그 14종
- `skills/donggu-deck/references/qa-headless.md` — 기계 검증이 필요할 때

## Boundary

- 산출물은 HTML 파일 하나. 폰트·이미지는 `assets/`에 로컬로 두고 외부 CDN을 부르지 않는다.
- 외부 디자인 문서(`DESIGN.md` 등)는 정본이 아니라 입력 원료 — 색·브랜드 값만 흡수하고 글자 크기·모션 지시는 계약으로 치환한다.
- 숫자는 실측만. 검증되지 않은 수치는 "근사" 표기 또는 로드맵으로.
- 이전 `donggu-docs:make-ppt`(범용 무드 탐색·PPTX 변환)는 2026-10-26에 폐지했다. 이 플러그인은 동구 스타일 덱 하나만 제공한다.

## Install

```
/plugin marketplace add donggu1105/donggu-skills
/plugin install donggu-ppt@donggu-skills
```

## Dependencies

- 없음(브라우저만). 기계 검증 시 헤드리스 Chrome.
- 폰트: Pretendard Variable(OFL) `assets/PretendardVariable.woff2` 동봉.

## License

[MIT](../LICENSE) © 2026 강동현 (donggu)
