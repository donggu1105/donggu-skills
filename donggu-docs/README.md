# donggu-docs

> Document & deck authoring skill collection — part of [`donggu-skills`](../) marketplace.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Skills](https://img.shields.io/badge/skills-2-green)](#-skills)

강의·세미나·워크샵·런칭 발표에서 쓸 **의존성 0 단일 HTML 덱**과, 링크드인·인스타그램용 **카드뉴스(캐러셀) 세트**를 만드는 스킬 모음. PPT보다 가볍고, 브라우저(Chrome)만 있으면 어디서나 만들고 발표할 수 있다.

---

## 📚 Skills

| Skill | 호출 | 사용 시점 | Output |
|---|---|---|---|
| **make-ppt** | `donggu-docs:make-ppt` | 강의·세미나·발표 덱 빌드, PPTX→웹 변환, 기존 HTML 덱 개선 | 의존성 0 단일 HTML 덱 |
| **make-card-news** | `donggu-docs:make-card-news` | 확정 원고 → 카드뉴스/캐러셀 (링크드인 문서 게시물, 인스타·스레드 캐러셀) | 1080×1350 PNG 세트 + PDF + 편집용 JSON 스펙 |

---

## 🃏 `make-card-news`

확정 원고를 **카드뉴스 세트**로 만든다. 글자는 이미지에 굽지 않고 HTML/CSS로 렌더링해서, 한 장만 고쳐 다시 뽑을 수 있다.

```text
spec.json (카드별 내용)  +  themes/<name>.json (색·폰트)  +  templates/card.html
        ↓  scripts/render_cards.py  (headless Chrome 스크린샷)
01.png … NN.png (1080×1350, 인스타·스레드)  +  cards.pdf (링크드인 문서 게시물)  +  qa.json (잘림·겹침·안전영역·폰트 검사)
```

- 카드 유형 8종: `cover` `stat` `point` `quote` `list` `steps` `compare` `closing` — 형식·한도는 `references/card-spec.md`
- 레이아웃 2종: `cinematic`(기본 — 전 장 사진 전면 + 어두운 그라데이션 + 흰 글자, 선·라벨·페이지 번호 없음), `classic`(흰 바탕 + 워시 + 밴드 사진)
- 사람 사진: 얼굴 박스 기준으로 크롭을 고르고(글자 위 여백 ≥70px 또는 글자 아래 묻힘), 식별 가능한 참가자는 `content-rights-clearance`로 판정해 노트에 남긴다. 이미지 안 가짜 버튼·URL은 검증에서 거부
- 볼트 적재: `scripts/vault_handoff.py` — qa 통과 세트를 Obsidian 볼트의 `Attachments/<날짜> - <제목> (카드뉴스)/`(PNG·PDF·cards.json·사진·MANIFEST 해시)와 채널 원고 노트(`channel_pack`, draft)로 넣고 INDEX 줄을 더한다. 기존 노트는 덮어쓰지 않음
- 테마: `beyond-deploy`(BD 메일 디자인 토큰), `donggu`(개인 채널). 새 톤은 테마 파일로 추가
- 원고 작성은 `donggu-sns:writing-social-content`, 발행은 `donggu-sns:publish-sns`가 맡는다. 이 스킬은 파일만 만든다
- 의존성: Chrome/Chromium(`$CARD_NEWS_CHROME`로 지정 가능), PDF 병합에 Pillow. Playwright·SaaS 없음
- 서비스형 대안(Gamma·망고보드·PostNitro…) 비교는 `references/tool-landscape.md`

```bash
python3 donggu-docs/skills/make-card-news/scripts/render_cards.py \
  donggu-docs/skills/make-card-news/examples/sample-bd.json --out ./out --theme beyond-deploy
python3 donggu-docs/skills/make-card-news/scripts/vault_handoff.py \
  spec.json --out ./out --title "제목" --channel instagram --source-url URL --dry-run
```

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

---

## 📜 License

[MIT](../LICENSE) © 2026 강동현 (donggu)

`make-ppt`는 `frontend-slides` 스킬을 베이스로 한 donggu 버전이며, `.md`-구동 경로를 추가했다. 베이스 스킬의 라이선스는 `make-ppt/LICENSE` 참조.
