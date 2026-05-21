# donggu-docs

> Document & deck authoring skill collection — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-1-green)](#-skills)

강의·세미나·워크샵·런칭 발표에서 쓸 **의존성 0 단일 HTML 덱**을 만드는 스킬 모음. PPT보다 가볍고, 브라우저만 있으면 어디서나 발표 가능.

---

## 📚 Skills

| Skill | 호출 | 사용 시점 | Output |
|---|---|---|---|
| **make-ppt** | `donggu-docs:make-ppt` | 강의·세미나·발표 덱 빌드, PPTX→웹 변환, 기존 HTML 덱 개선 | 의존성 0 단일 HTML 덱 |

---

## 🎬 `make-ppt`

`frontend-slides` 스킬을 베이스로, **`.md`-구동 경로**를 더한 donggu 버전.

스타일을 정하는 방법이 둘:

1. **비주얼 디스커버리** — 무드 → 프리뷰 3장 → 선택. (frontend-slides 기본)
2. **`.md`-구동** — 프로젝트 `./designs/` 폴더의 `DESIGN.md`가 룩을 결정. 디자인 시스템이 이미 있거나 특정 브랜드/미감을 원할 때.

공통 — 의존성 0 단일 HTML, 슬라이드마다 정확히 `100vh`(스크롤 금지), 차별화된 디자인(AI슬롭 회피). PPTX 변환·PDF·배포 지원.

### designs/ 라이브러리 (.md-구동)

```
designs/
  <name>/
    DESIGN.md     디자인 시스템 — 색·폰트·간격·컴포넌트·규칙 (룩의 기준)
    fonts.md      폰트 매핑 + 웹폰트 <link>
    <deck>.md     (선택) 덱 콘텐츠 — 슬라이드별 내용
```

`.md` 두 개 — `DESIGN.md`(룩) + content `.md`(내용) — 가 덱을 정의하고, make-ppt가 자기완결 단일 HTML로 합성한다. getdesign.md 같은 곳에서 받은 `DESIGN.md`를 그대로 쓸 수 있다. 형식·변환 규칙은 `make-ppt/designs-md-guide.md` 참조.

### 구성

```
make-ppt/
├── SKILL.md               # 6단계 워크플로우 (+ .md-구동 경로)
├── viewport-base.css      # 필수 — 뷰포트 피팅 CSS
├── html-template.md       # 덱 HTML 구조 + JS
├── animation-patterns.md  # 애니메이션 레퍼런스
├── STYLE_PRESETS.md       # 12개 비주얼 프리셋 (비주얼 디스커버리용)
├── designs-md-guide.md    # .md-구동 — designs/ 형식 + DESIGN.md→CSS 변환
└── scripts/
    ├── extract-pptx.py    # PPTX 콘텐츠 추출
    ├── export-pdf.sh      # PDF 내보내기
    └── deploy.sh          # Vercel 배포
```

---

## 🎯 사용 가정

- 의존성 0 단일 HTML 덱이 필요함 (PPT·Keynote 대체) — 브라우저만 있으면 발표 가능.
- 잠긴 템플릿이 아니라 콘텐츠·디자인에 맞춰 자유롭게 슬라이드를 구성.
- 디자인 시스템(`DESIGN.md`)이 있으면 그걸 룩의 기준으로, 없으면 비주얼 디스커버리로.

---

## 🔗 관련

- [donggu-skills marketplace](../) — 본 plugin 부모
- [donggu-obsidian](../donggu-obsidian/) — vault 콘텐츠 추출 후 본 스킬로 발표 자료화

---

## 📜 License

[MIT](../LICENSE) © 2026 강동현 (donggu)

`make-ppt`는 `frontend-slides` 스킬을 베이스로 한 donggu 버전이며, `.md`-구동 경로를 추가했다. 베이스 스킬의 라이선스는 `make-ppt/LICENSE` 참조.
