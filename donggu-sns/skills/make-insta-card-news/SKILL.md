---
name: make-insta-card-news
description: Use when the user asks for 카드뉴스, Instagram carousel images, 인스타 캐러셀, SNS 카드 이미지, or converting a post/article into card images — especially when a DESIGN.md (getdesign.md format) or designs/ folder should drive the look. Also use for blog hero/대표이미지 in the same brand look.
---

# make-insta-card-news

글(블로그 마스터·인스타 팩·아무 .md)을 **DESIGN.md가 정의한 브랜드 룩**의 인스타 카드뉴스 PNG 세트(1080×1350, 4:5)로 변환한다. 렌더는 HTML 템플릿 + Playwright 스크린샷 — 텍스트를 이미지 모델로 "그리지" 않는다(한글 오타 0%가 목표).

**핵심 분리: 워크플로(이 스킬, 불변) vs 룩(DESIGN.md, 교체 가능).** 취향이 바뀌면 DESIGN.md만 바꾼다. 스킬은 건드리지 않는다.

## Workflow

### 1. Intake
- **콘텐츠**: 원문 .md (Obsidian 인스타 팩이면 카드 분배가 이미 있을 수 있음 — 그대로 존중).
- **DESIGN.md**: `./DESIGN.md` → `./designs/*/DESIGN.md` 순으로 탐색. 없으면 사용자에게 묻는다: getdesign 카탈로그(`npx getdesign@latest add <name>`) / 직접 붙여넣기 / 기본 한국 정석 스타일(kr-card-principles.md만으로 진행).
- **장수**: 기본 표지 + 본문 3~5 + CTA. 사용자가 지정하면 그대로.

### 2. Page Plan
표지 = 훅 한 방. 본문 카드 = **1카드 1아이디어**. 마지막 = CTA(프로필 링크·블로그). 각 카드에 layout-recipes.md의 골격 하나를 배정해 내부 플랜을 만든다. 사용자가 검토를 원하면 플랜을 먼저 보여준다.

### 3. DESIGN.md → 카드 CSS (hard rules)
- **토큰 → `:root` 변수.** DESIGN.md가 토큰화한 hex를 인라인으로 쓰지 않는다.
- **타이포 스케일 업**: DESIGN.md의 px는 웹 스케일. 카드(1080px가 폰에서 ~400px로 보임)에선 **위계와 비율은 유지, 절대값은 ×1.4~2** (display 80→112~160px, body 16→28~36px). 본문 28px 미만 금지.
- **Do's/Don'ts는 제약 조건이다.** "그라디언트 금지", "radius 0" 같은 조항을 어기면 실패. 표지부터 CTA까지 전부 적용.
- **한글 보정 필수**: kr-card-principles.md를 함께 적용 (폰트 대체·`word-break: keep-all`·UPPERCASE는 라틴 라벨에만).
- 사진이 핵심인 시스템(full-bleed photography 등)인데 사진이 없으면 — 시스템의 **타이포·표면·헤어라인 문법**으로 대체하고, 그 갭을 사용자에게 한 줄로 알린다. 웹에서 임의 이미지를 긁어오지 않는다.

### 4. Build
`card-template.html`을 작업 폴더(`<프로젝트>/cardnews-<slug>/` 또는 /tmp)에 복사 → `:root` 토큰 채우기 → `<!-- CARDS_HERE -->`에 카드 `<section class="card" id="card-N">` 추가. 템플릿의 클래스 골격을 벗어나는 커스텀 CSS는 태스크 블록 하나에 모은다.

### 5. Render
```bash
cd <작업폴더> && python3 -m http.server 8765 &
```
Playwright로 `http://localhost:8765/index.html` 열고 **카드 노드별 element screenshot** (`#card-N` → `card-N.png`). 뷰포트 크기 무관 — 노드가 1080×1350이면 PNG도 정확히 그 크기. 끝나면 서버 종료.

### 6. QA & Deliver
- 렌더된 PNG를 Read로 직접 확인: 한글 폰트 적용? 오버플로/푸터 충돌? DESIGN.md Don'ts 위반?
- 360px로 줄여도 표지 타이틀이 읽히는가(썸네일 테스트).
- 결과물 경로 + 적용한 DESIGN.md + 의도적으로 어긴 것 없음(또는 갭)을 보고. 디스코드 전송 요청이 있으면 봇 토큰으로 첨부 업로드.

## Hard Rules
- 텍스트가 들어가는 모든 요소에 `word-break: keep-all`.
- 카드 푸터는 flex column + `margin-top: auto`로 고정 — absolute 금지(내용과 충돌).
- 이모지·픽토그램은 DESIGN.md가 장식을 허용할 때만 포인트로. 장식 금지 시스템(BMW류)에선 안 쓴다.
- 시드 템플릿 없이 빈 HTML에서 시작하지 않는다.

## Files
- `card-template.html` — 검증된 시드 (토큰 슬롯 + 카드 보드 + 푸터 패턴)
- `kr-card-principles.md` — 한국어/한국 카드뉴스 보정 규칙 (폰트 대체표·크기 위계·정석 팁)
- `layout-recipes.md` — 카드 골격 5종 (cover / numbered / rows / quote / cta)
