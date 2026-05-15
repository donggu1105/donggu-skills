# donggu-docs

> Document & deck authoring skill collection — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-1-green)](#-skills)
[![Based on](https://img.shields.io/badge/based%20on-tightened--slide-blue)](https://github.com/bytonylee/future-slide-skill)

강의·세미나·워크샵·런칭 발표에서 쓸 **단일 HTML 덱**을 22개 잠긴 레이아웃 + 4개 테마 + 검증기 기반으로 만드는 스킬 모음. PPT보다 가볍고, 매번 같은 톤이 나오는 시스템이 필요할 때.

---

## 📚 Skills

| Skill | 호출 | 사용 시점 | Output |
|---|---|---|---|
| **make-ppt-slide** | `donggu-docs:make-ppt-slide` | 강의·세미나·워크샵·런칭 덱 빌드. PPT 대신 가벼운 HTML 덱이 필요할 때 | 단일 `index.html` + 인접 `images/` + 검증 통과 |

---

## 🧬 Skill 상세

### 🎬 `make-ppt-slide`

가로 스와이프 단일 HTML 덱을 만든다. 키보드(`←`/`→`/`ESC`/`B`)로 발표 모드 전환. 브라우저만 있으면 어디서나 발표 가능.

**잠긴 시스템 3겹**:

1. **구조 락**: `S01`~`S22` 22개 + 표지·클로징 2개 = 24개 페이지 타입. 새 레이아웃 발명 금지.
2. **시각 락**: 4개 컬러 테마 (Klein Blue / Lemon Yellow / Lemon Green / Safety Orange), 액센트 1개만, `200`/`300` 폰트 웨이트, 직선 사각형, 그림자·그라디언트·둥근 카드 금지.
3. **검증 락**: `node scripts/validate-deck.mjs` 통과 강제 — 미등록 레이아웃·SVG 가시 텍스트·`data-image-slot` 누락 등 9가지 위반 자동 차단.

**자료 구조**:

```
make-ppt-slide/
├── SKILL.md                    # 7스텝 워크플로우
├── assets/
│   ├── template.html           # 376줄 골격 (CSS 토큰 + 24개 레이아웃 클래스)
│   └── motion.min.js           # 애니메이션 라이브러리
├── references/
│   ├── layouts.md              # 22개 레이아웃 카탈로그 + 강의 매핑 가이드
│   ├── layout-lock.md          # 구조 계약 + 이미지 슬롯 규칙
│   ├── themes.md               # 4개 컬러 프리셋
│   ├── checklist.md            # 배포 전 체크리스트
│   ├── image-prompts.md        # 이미지 슬롯별 프롬프트
│   └── map-component.md        # S08 우측 슬롯 지도 컴포넌트
└── scripts/
    └── validate-deck.mjs       # 정규식 기반 검증기
```

**언어 모드**: 한국어(`ko`) / 영어(`en`). 강의 콘텐츠 기본 = `ko` (SUIT·Pretendard·Noto Sans KR 폰트 스택).

---

## 🎯 사용 가정

- 단일 `index.html` 가로 스와이프 덱이 필요함 (PPT·Keynote 대체).
- 발표가 시리즈로 이어질 가능성 있음 → 매번 같은 톤이 자동 보장되는 시스템 필요.
- 본문 톤이 비즈니스 덱보다 **강의·교육·세미나·워크샵**에 가까움.
- 액센트 컬러 1개를 받아들일 수 있는 미니멀 비주얼 취향.
- 이미지는 본인 자산(강사 사진, 강의장 스크린샷)을 로컬에서 박는 방식을 우선. AI 이미지 생성은 옵션.

> 비즈니스 덱(투자자·세일즈·런칭) 톤이 필요하면 원본 [`tightened-slide`](https://github.com/bytonylee/future-slide-skill)를 그대로 쓰는 것도 가능. 본 스킬은 그 시스템을 강의 콘텐츠 톤으로 재작성한 donggu 버전.

---

## 💡 활용 시나리오

### 강의 1회 빌드 (30-90분)

```
1. vault에서 강의 핵심 메시지·사례·원리 정리
2. /donggu-docs:make-ppt-slide
   → 청중·시간·자료·언어·테마 명세 (최대 3 질문)
   → 페이지 계획 표 → 레이아웃 선택 → HTML 생성
3. node scripts/validate-deck.mjs path/to/index.html  (자동 검증)
4. 브라우저에서 시각 점검 (사용자 직접)
```

### 강의 시리즈 빌드 (3-7일, 자산화)

```
1. /donggu-obsidian:extract-core    (각 강의 핵심 CORE 추출)
2. /donggu-docs:make-ppt-slide      (CORE 입력 → 강의별 덱)
3. 시리즈 전체 톤 일관성 자동 보장 (같은 22 레이아웃 + 같은 테마)
4. 발표 후 retro → vault에 반영 → 다음 회차 자료가 누적됨
```

### 세미나·워크샵 직전 빌드 (1-2시간)

```
1. /donggu-docs:make-ppt-slide
   → "오즈 2026-05 세미나용 60분 강의 덱, 한국어, IKB 테마"
   → 8-12 페이지 권장 (강사 STAR Moment + 약력 + 실습 안내 포함)
2. 검증 + 브라우저 리허설
3. 발표 모드 B 동작 확인 (강사 노트 가림)
```

---

## 🔗 관련

- [donggu-skills marketplace](../) — 본 plugin 부모
- [원본 tightened-slide](https://github.com/bytonylee/future-slide-skill) — 본 시스템의 출처 (Apache-2.0)
- [donggu-obsidian](../donggu-obsidian/) — vault 콘텐츠 추출 후 본 스킬로 발표 자료화

---

## 📜 License

[MIT](../LICENSE) © 2026 강동현 (donggu)

원본 `tightened-slide`는 [Apache-2.0](https://github.com/bytonylee/future-slide-skill/blob/main/LICENSE). 본 donggu 버전은 그 라이선스를 준수하며 한국어/강의 콘텐츠 톤으로 재작성한 derivative work.
