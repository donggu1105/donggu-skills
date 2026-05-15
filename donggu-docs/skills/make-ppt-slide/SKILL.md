---
name: make-ppt-slide
description: 가로 스와이프 단일 HTML 덱(`index.html`)을 잠긴 22개 레이아웃(S01~S22) + 4개 테마 + 검증기 기반으로 정교하게 만든다. 사용자가 강의/세미나/워크샵/런칭/리서치/제품 덱을 요청하거나, vault 노트에서 슬라이드를 빌드하거나, "발표 자료 만들어줘", "덱 만들어줘", "PPT 대신 HTML 슬라이드", "딥리뷰 슬라이드"라고 말할 때 사용.
---

# make-ppt-slide

가로 스와이프 단일 HTML 덱을 만드는 스킬. 강의·세미나·워크샵·런칭·분석·리서치 덱을 22개 잠긴 레이아웃과 4개 컬러 테마, 검증기 기반으로 일관되게 빌드한다.

> 원본: [bytonylee/future-slide-skill](https://github.com/bytonylee/future-slide-skill) `tightened-slide`. 본 스킬은 그 시스템을 한국어/강의 콘텐츠 톤으로 옮긴 donggu 버전.

## 운영 가정

- 출력은 단일 `index.html`(가로 스와이프 덱) + 인접 `images/` 폴더.
- 템플릿은 `assets/template.html`.
- 본문 슬라이드는 등록된 `S01`~`S22` 레이아웃만 사용. 새 구조 발명 금지.
- 전달 전 `node scripts/validate-deck.mjs path/to/index.html` 통과 강제.
- 언어 모드는 한국어(`ko`)·영어(`en`) 둘 다 지원. 강의 콘텐츠 기본은 `ko`.

## Step 1: 필요한 것만 묻기

사용자가 자료·목적을 충분히 줬으면 바로 진행. 부족하면 **최대 3개**만 묻는다.

1. 청중과 발표 상황(강의실/온라인/세미나/내부 발표).
2. 목표 시간 또는 페이지 수.
3. 원자료, 언어 모드, 필요한 이미지·데이터, 강한 제약(브랜드 컬러, 시간, 인원 등).

테마 미지정 시 기본 = `International Klein Blue` (`references/themes.md` 참조).
언어 모드 미지정 시 기본 = `ko`.

## Step 2: 덱 디렉토리 준비

```bash
mkdir -p path/to/deck/images
cp assets/template.html path/to/deck/index.html
```

`<title>` 자리표시자는 즉시 실제 제목으로 교체.

루트 엘리먼트에 언어 모드 표기:

```html
<html lang="ko" data-language="ko">
```

또는

```html
<html lang="en" data-language="en">
```

한국어 모드는 `SUIT`, `Pretendard`, `Noto Sans KR`, `Noto Sans` 폰트 스택을 우선 사용한다.

오프라인 발표를 대비하려면 `assets/motion.min.js`를 함께 복사. 안 하면 템플릿 내장 CDN fallback이 작동한다.

## Step 3: Preflight (마크업 작성 전)

다음을 **반드시** 먼저 읽는다:

- 템플릿의 `<style>` 블록 (사용 가능한 CSS 클래스 카탈로그).
- `references/layout-lock.md` (구조 계약).
- 쓰려는 레이아웃의 스켈레톤 (`references/layouts.md`).

쓰려는 모든 클래스가 템플릿에 존재하는지 확인. 글로벌 클래스 발명 금지. 인라인 스타일은 페이지별 미세 조정에만 사용.

마크업 전에 페이지 계획 표를 작성:

```text
page -> data-layout -> reason -> image slot
```

레이아웃 다양성:

- 7~8페이지 덱 → 최소 6개 서로 다른 `Sxx` 사용.
- 10페이지 이상 덱 → 최소 8개 서로 다른 `Sxx` 사용.

## Step 4: 레이아웃 선택

등록된 22개 + 표지/클로징 2개 중에서만 선택. 자세한 사용 가이드는 `references/layouts.md`.

핵심 매핑:

- 표지·섹션 오프너 → `S01`
- 명제·챕터 선언 → `S03`, `S09`, `S10`
- 비교(전/후, A/B) → `S08`. 지도·동선은 `S08 + Tightened Map Component` (`references/map-component.md`)
- 4·6·3개 동급 → `S19`, `S04`/`S16`, `S05`/`S13`
- 선형 프로세스 → `S11`. 루프 → `S14`.
- 정량 → `S06`(4개), `S07`(랭킹), `S20`(ledger), `S21`(스펙)
- 큰 이미지 1개 → `S22`. 여러 이미지 → `S15`/`S16` 적응.

## Step 5: 시각 시스템 적용

하드 룰:

- 덱당 액센트 컬러 1개.
- 그라디언트·그림자·둥근 카드·글래스·네온·3D·장식적 보더 금지.
- 큰 타이포는 `font-weight:200` 또는 `300`.
- 큰 폰트 사이즈는 `font-size:min(Xvw,Yvh)`, `Y >= X * 1.6`.
- 본문 타이틀은 좌측·상단 콘텐츠 축에 정렬. 단 statement/split 레이아웃은 예외.
- 카테고리·메타 텍스트는 타이틀 *위에* 배치, 옆에 X.
- `.canvas-card`에 이미 패딩이 있으니 내부에 또 `5vw` 패딩 추가 금지.
- 캡션·각주·라벨은 하단 네비게이션 안전 영역 위에.
- SVG는 도형만 그린다. 가독 라벨은 HTML로.

언어 룰:

- 한국어 모드: 짧은 한국어 타이틀, 컴팩트한 본문, 일관된 제품·기술 용어.
- 영어 모드: concise sentence case 타이틀, 짧은 본문.
- 다이어그램 라벨·생성 이미지 내 텍스트는 선택한 언어 모드와 일치.

## Step 6: 이미지 흐름 (필요할 때만)

donggu 운영 원칙: **AI 이미지 생성보다 본인 자산(강의 사진, 강의장 스크린샷, 작품 이미지)을 로컬에서 `images/`에 직접 박는 방식을 우선**한다. 22개 레이아웃 중 19개는 이미지 없이 완성된다.

이미지가 필요하면:

- 생성·배치 전에 레이아웃 슬롯을 먼저 정한다 (`s22-hero-21x9`, `s15-grid-21x9` 등).
- 자세한 슬롯 규칙은 `references/image-prompts.md`.
- 모든 로컬 이미지에 `data-image-slot` 속성 필수.
- 파일명 규약: `{page}-{semantic-name}.{ext}` (예: `05-keynote-stage.jpg`).
- 같은 그룹 이미지는 비율·시각 스케일·여백 밀도 통일.

## Step 7: 검증 + 브라우저 점검

```bash
node scripts/validate-deck.mjs path/to/index.html
```

에러는 전부 수정. 경고는 시각 점검.

브라우저에서 다음을 직접 확인 (이건 **사용자 본인이 검증**):

- 타이틀 정렬, 폰트 웨이트, 타이틀-본문 간격.
- 이미지 크롭과 슬롯 적합도.
- 캡션·각주가 네비게이션 닷 위에 있는지.
- `ESC` 인덱스 가시성, `B` 정적 모드 작동.

배포 전 최종 체크리스트는 `references/checklist.md`.

## 자료 참조

| 파일 | 용도 |
|---|---|
| `references/layouts.md` | 22개 레이아웃 정의·언제 쓰는지·CSS 클래스 |
| `references/layout-lock.md` | 구조 계약 표 + 이미지 슬롯 규칙 |
| `references/themes.md` | 4개 컬러 프리셋 (Klein Blue / Lemon Yellow / Lemon Green / Safety Orange) |
| `references/image-prompts.md` | 이미지 생성이 필요할 때 슬롯별 프롬프트 |
| `references/map-component.md` | S08 우측 슬롯 지도 컴포넌트 |
| `references/checklist.md` | 배포 전 체크리스트 |

## 관련 Skill

- `donggu-obsidian:extract-core` — 빌드 저널에서 atomic CORE 노트를 뽑은 뒤, 그 CORE들을 입력으로 본 스킬을 호출하면 강의 덱 빌드가 자연스럽게 이어진다.
- `donggu-obsidian:checking-vault-health` — Channel Pack 출구가 막혔는지 점검 후 본 스킬로 발표 자료화.
