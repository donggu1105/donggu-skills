# 레이아웃 락 (구조 계약)

본 문서는 덱의 **구조 계약**이다. 페이지가 시각적으로는 비슷해 보이지만 미등록 구조를 쓰는 일을 막는다.

## 생성 규칙

1. 모든 본문 슬라이드는 마크업 전에 등록된 레이아웃 하나를 정한다.
2. 모든 `<section class="slide">`에는 `data-layout="Sxx"` 또는 허용된 표지·클로징 ID가 있어야 한다.
3. 새 본문 구조 발명 금지.
4. 큰 비주얼 1개는 `S22 Image Hero`.
5. 여러 비주얼은 `S15`·`S16` 그리드 적응.
6. 지도·동선·로케이션 네트워크는 `S08 + Tightened Map Component`.
7. 본문 타이틀은 좌측·상단 콘텐츠 축. 단 등록된 statement·split 레이아웃은 예외.
8. SVG는 도형만. 가시 라벨은 HTML.
9. 이미지를 생성·배치하기 전에 슬롯을 먼저 결정.

## 등록된 레이아웃

| ID | 이름 | 필수 스켈레톤 | 이미지 규칙 |
|---|---|---|---|
| S01 | Index Cover | `cover-row` 3행, 큰 인덱스 + 타이틀 | 없음 |
| S02 | Vertical Timeline + KPI | 상단 타이틀, `.timeline-v`, 하단 `.kpi-row-4` | 없음 |
| S03 | Split Statement | `.slide.split` 좌측 큰 진술 + 우측 설명 | 없음 |
| S04 | Six Cells | 상단 타이틀 + `.sub-grid-3-2` 6셀 | 작은 아이콘만 |
| S05 | Three Layers | 상단 타이틀 + `.stack-row` 3블록 | 없음 |
| S06 | KPI Tower | 좌측 타이틀, 우측 노트, 불균등 KPI 타워 | 없음 |
| S07 | Horizontal Bar | 좌측 정렬 타이틀 + 수평 막대 리스트 | 없음 |
| S08 | Duo Compare | `.duo-compare` 2컬럼 + 중앙 룰 | 우측 슬롯에 map 컴포넌트 대체 가능 |
| S09 | Dot Matrix Statement | 큰 진술 + dot matrix 장식 | 없음 |
| S10 | Split Closing | `.slide.split` 좌측 진술 + 우측 takeaway 리스트 | 없음 |
| S11 | Horizontal Timeline | 헤더 + `.timeline-h` | 없음 |
| S12 | Manifesto + Ink Banner | 큰 진술 + 풀폭 잉크 배너 | 없음 |
| S13 | Three Forces | 좌측 잉크 히어로 + 우측 3 카드 | 없음 |
| S14 | Loop Form | 좌측 스텝 + 우측 기하 루프 | SVG 도형만 |
| S15 | Matrix + Hero Stat | 매트릭스 그리드 + 하단 hero stat | 다중 이미지 적응 |
| S16 | Multi-card Brief | 3×2 brief 카드 | 다중 이미지 카드 적응 |
| S17 | System Diagram | 헤더 + 기하 시스템 다이어그램 + 하단 노트 | SVG 도형만 |
| S18 | Why Now | 3 점진 컬럼 + 하단 숫자 | 없음 |
| S19 | Four Cards | 상단 액센트 룰 + 4 동일 카드 | 없음 |
| S20 | Stacked KPI Ledger | 큰 숫자의 수직 ledger 행 | 없음 |
| S21 | Tech Spec Sheet | 큰 타이틀, KPI 행, 수직 막대 매트릭스 | 없음 |
| S22 | Image Hero | 풀폭 상단 이미지, 타이틀 블록, 하단 KPI 행 | 메인 이미지 `21:9` 필수 |

## 이미지 슬롯 규칙

### S22 Hero Strip

- 슬롯: `s22-hero-21x9`.
- 비율: `21:9`.
- 용도: 실제 장면·제품·UI·강의장·연사 사진.
- 주제는 중앙 안전 영역에 위치.
- 사진은 `object-fit:cover`, `object-position:center 35%` 또는 `center center`.
- 고밀도 UI나 인포그래픽 이미지는 필요시에만 `object-fit:contain`.

### S15·S16 이미지 그리드

- 그룹당 비율 1개: `21:9` 또는 `16:10`.
- 그룹당 시각 스케일 1개.
- 재생성 슬롯 이미지는 `.frame-img.r-21x9` 또는 `.frame-img.r-16x10`.
- `.fit-contain`은 통제 불가 스크린샷·고밀도 텍스트 이미지에만.

## 금지 패턴

- `data-layout` 누락.
- 미등록 본문 페이지.
- 등록된 statement·split 외에서 본문 타이틀 가운데 정렬.
- SVG `<text>` 가시화.
- `data-image-slot` 없는 이미지.
- 둥근 이미지 컨테이너·그림자·그라디언트·글래스 효과.
- S22 사진에 `object-position:top center` (얼굴 잘림 방지).
