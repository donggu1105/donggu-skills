# 레이아웃 카탈로그 (S01~S22)

본 스킬에 등록된 레이아웃과 사용 시점을 정의한다. **본문 슬라이드는 반드시 `S01`~`S22` 중에서만 선택**. 새 구조를 발명하지 않는다.

## 베이스라인

- 영어 모드 폰트: Inter, Helvetica, Arial, system sans.
- 한국어 모드 폰트: SUIT, Pretendard, Noto Sans KR, Noto Sans.
- 덱당 액센트 컬러 1개.
- 마크업이 로컬 CSS 그리드를 쓰더라도 사고는 12/16 컬럼 그리드 기준.
- 직선 사각형, 헤어라인 1px, 넉넉한 여백.
- 그라디언트·그림자·둥근 카드·글래스·네온·장식 보더 금지.
- 큰 타이포는 `font-weight:200` 또는 `300`. 본문은 보통 `300`, 작은 카테고리 라벨은 `600`.
- 큰 폰트 사이즈는 `min(Xvw,Yvh)`로 `vh` 헤드룸 확보.
- 카테고리·메타 텍스트는 타이틀 *위*에. 옆에 두지 않는다.
- `.canvas-card`가 이미 페이지 패딩을 제공. 내부에 또 풀폭 패딩 레이어를 두지 않는다.
- 캡션·각주·하단 라벨은 네비게이션 안전 영역 위.
- SVG는 도형만. 읽혀야 하는 라벨은 HTML로.

## 언어 모드

영어:

- `<html lang="en" data-language="en">`.
- concise sentence case 타이틀.
- 라벨·다이어그램 텍스트는 가능하면 8단어 이내.

한국어:

- `<html lang="ko" data-language="ko">`.
- 컴팩트한 한국어 타이틀, 짧은 본문 줄.
- 제품명·기술 용어는 덱 전체에서 일관.

## 페이지 계획 표

마크업 전에 다음 표를 먼저 작성:

```text
page -> data-layout -> reason -> image slot
```

예시 (7페이지 강의 덱):

```text
01 -> S01 -> 오프닝 + 주제 프레임 -> none
02 -> S03 -> 핵심 명제 -> none
03 -> S08 -> 흔한 오해 vs 실제 -> none
04 -> S14 -> 학습 루프 모델 -> none
05 -> S22 -> 사례 증거 사진 -> s22-hero-21x9
06 -> S13 -> 세 가지 원리 -> none
07 -> S10 -> 마무리 + 행동 제안 -> none
```

## 레이아웃 다양성 규칙

- 7~8페이지 덱은 최소 6개 서로 다른 `Sxx` 사용.
- 10페이지 이상 덱은 최소 8개 서로 다른 `Sxx` 사용.
- 같은 본문 구조의 페이지를 3장 연속 배치 금지.
- 시범 덱은 표지·클로징·비교 또는 타임라인·구조 다이어그램·이미지 레이아웃을 최소 하나씩 포함.

## 등록된 레이아웃

### S01 Index Cover

표지·섹션 오프너. 타이틀·서브타이틀·메타데이터를 담는다. 굵고 희소하고 강하게 구조화.

추천 클래스: `.slide.accent`, `.canvas-card`, `.chrome-min`, `.ascii-bg`, `.h-hero`, `.lead`.

### S02 Vertical Timeline + KPI

시간에 따른 변화를 실제 수치 신호와 함께 보여줄 때. 각 노드에 날짜/단계 + 지표 + 짧은 설명. 수치 없으면 `S11` 사용.

추천 클래스: `.timeline-v`, `.tl-node`, `.tl-axis`, `.dot`, `.kpi-row-4`.

### S03 Split Statement

명제·챕터 선언·강한 주장. 왼쪽에 큰 아이디어, 오른쪽에 짧은 해설.

추천 클래스: `.slide.split`, `.half`, `.b-ink`, `.b-paper`, `.h-statement`.

### S04 Six Cells

정확히 6개의 동급 아이템: 개념·기능·원리·짧은 정의. 4개나 5개를 억지로 끼우지 않는다.

추천 클래스: `.sub-grid-3-2`, `.card-fill`, `.t-cat`, `.body-sm`.

### S05 Three Layers

세 단계·세 층·중간 분량 설명을 가진 세 개 동급 아이디어.

추천 클래스: `.stack-row`, `.card-fill`, `.h-md`, `.lead`.

### S06 KPI Tower

비교 가능한 4개 정량 지표. 막대 높이가 실제 데이터를 반영해야 한다. 질적 기능 리스트엔 쓰지 않는다.

추천 클래스: `.kpi-tower-row`, `.bar-tower`, `.card-outlined`.

### S07 Horizontal Bar

5~10개의 랭킹된 또는 비례 값. 모든 막대에 실제 비교 가능한 값.

추천 클래스: `.h-bar-chart`, `.bar-row`, `.bar-fill`.

### S08 Duo Compare

전/후, 구/신, 모델 A/모델 B, 두 트랙 설명. 양쪽이 구조적으로 평행해야 한다.

추천 클래스: `.duo-compare`, `.vrule`, `.card-fill`.

지도·경로·동선 네트워크에는 `S08 + Tightened Map Component` (`map-component.md`) 사용.

### S09 Dot Matrix Statement

두 번째 선언 페이지 또는 시각적 호흡. 압축된 주장을 담는다. 데이터 테이블·긴 단락 금지.

추천 클래스: `.dot-mat`, `.h-statement`, `.t-meta`.

### S10 Split Closing

마무리 근처에서 1회 사용. 왼쪽에 최종 진술, 오른쪽에 짧은 세 가지 take-away.

추천 클래스: `.slide.split`, `.half`, `.b-accent`, `.closing-list`.

### S11 Horizontal Timeline

4~7스텝의 선형 프로세스·타임라인. 루프는 `S14`.

추천 클래스: `.timeline-h`, `.tl-h-node`, `.tl-h-axis`.

### S12 Manifesto + Ink Banner

섹션 종결 또는 덱 중반의 강한 결론. 주장 + 고대비 배너.

추천 클래스: `.manifesto-top`, `.ink-banner-full`.

### S13 Three Forces

정확히 3개의 풍부한 동급 아이디어. 각 카드 내부 구조가 동일.

추천 클래스: `.three-forces`, `.hero-ink-col`, `.force-card`, `.force-num`.

### S14 Loop Form

피드백 루프·자동화 루프·학습 루프·반복 사이클. 선형 시퀀스엔 쓰지 않는다.

추천 클래스: `.loop-diagram`, `.loop-steps`, `.loop-svg`.

### S15 Matrix + Hero Stat

8~12개의 동급 아이템 + 총합·요약 지표. 모든 이미지 슬롯이 같은 비율이면 다중 이미지 그리드로 적응 가능.

추천 클래스: `.matrix-fill`, `.matrix-cell`, `.hero-stat-bottom`, `.frame-img.r-21x9`.

### S16 Multi-card Brief

정확히 6개의 컴팩트한 노트·팁·작은 피처 카드. 6장 이미지 브리프 그리드로 적응 가능.

추천 클래스: `.brief-grid`, `.brief-card`, `.frame-img.r-21x9`.

### S17 System Diagram

엄격한 3-layer 시스템·생태계·아키텍처 맵. 라벨은 HTML, SVG 텍스트 금지.

추천 클래스: `.system-diagram`, `.sys-svg`, `.sys-label`.

### S18 Why Now

세 가지 이유, 각각 숫자·명확한 근거 뒷받침. 마지막 컬럼에 액센트.

추천 클래스: `.why-now-grid`, `.why-col`, `.why-num-bottom`.

### S19 Four Cards

정확히 4개의 동일한 피처·모듈. 카드 스타일 동일.

추천 클래스: `.four-cards`, `.fc-col`.

### S20 Stacked KPI Ledger

ledger 형태의 4~6개 핵심 지표. 각 행에 숫자·라벨·짧은 컨텍스트.

추천 클래스: `.stacked-ledger`, `.ledger-row`, `.ledger-num`.

### S21 Tech Spec Sheet

제품 스펙·벤치마크·모델 성능·고밀도 기술 증거. 실제 다차원 데이터 필요.

추천 클래스: `.tech-spec`, `.spec-title-col`, `.spec-kpi-grid`, `.spec-bars`, `.bar-vert`.

### S22 Image Hero

큰 비주얼 + 보조 지표 3개. 상단 이미지는 `21:9` 슬롯, `data-image-slot="s22-hero-21x9"`.

추천 클래스: `.image-hero-body`, `.image-hero-stats`, `.frame-img`, `.r-21x9`.

## 콘텐츠 → 레이아웃 인덱스

| 콘텐츠 모양 | 사용 | 피하기 |
|---|---|---|
| 표지·오프너 | S01 | 고밀도 데이터 레이아웃 |
| 명제·챕터 선언 | S03 또는 S09 | KPI 레이아웃 |
| 전/후 비교 | S08 | 6셀 그리드 |
| 동급 4개 | S19 | S04 |
| 동급 6개 | S04 또는 S16 | S19 |
| 동급 3개 | S05 또는 S13 | S04 |
| 선형 프로세스 | S11 | S14 |
| 루프·피드백 사이클 | S14 | S11 |
| 랭킹 정량 값 | S07 | 선언형 레이아웃 |
| 정량 4개 | S06 | 질적 카드 레이아웃 |
| 고밀도 제품 스펙 | S21 | 가벼운 선언 페이지 |
| 큰 비주얼 1개 | S22 | 미등록 분할 이미지 페이지 |
| 관련 비주얼 다수 | S15·S16 적응 | 미등록 evidence wall |
| 지도·동선 네트워크 | S08 map 확장 | 일반 카드 |
| 마무리 | S10 | 표지 구조 재활용 |

## 강의 콘텐츠 매핑 가이드

donggu vault에서 흔히 쓰는 콘텐츠 패턴을 어디에 매핑할지:

| 강의 패턴 | 권장 레이아웃 | 이유 |
|---|---|---|
| 한 줄 핵심 메시지 | S03 / S09 / S12 | 큰 진술을 호흡 있게 |
| 흔한 오해 → 실제 | S08 | 좌/우 비교 구조가 자연스러움 |
| 학습 루프·반복 의례 | S14 | 시작/끝 없는 사이클 표현 |
| 단계별 빌드(00→06 등) | S11 | 선형 타임라인 |
| 3가지 원리·관점 | S05 또는 S13 | 동급 3개 |
| 6가지 체크포인트 | S04 | 동급 6개 |
| 사례 사진 + KPI | S22 | 강사·강의장 사진 |
| 4 layer 시스템 | S17 | 입구·정제·출구·큐레이션 같은 구조 |
| 마무리 + 다음 액션 | S10 | 좌측 진술 + 우측 takeaway |

## 자주 나오는 실수

1. 카드·이미지 프레임에 `border-radius` 추가.
2. 그림자·그라디언트 추가.
3. SVG `<text>` 가시화.
4. 일반 본문 타이틀을 가운데 정렬.
5. 실데이터 없이 데이터 레이아웃 사용.
6. 모든 페이지에 같은 애니메이션 레시피.
7. 캡션을 네비게이션 닷에 너무 붙임.
8. `.canvas-card` 페이지 패딩을 본문 안에서 중복.
9. 한 그룹 안에 비율이 다른 이미지 혼용.
10. 슬롯을 정하기 전에 이미지부터 생성.
