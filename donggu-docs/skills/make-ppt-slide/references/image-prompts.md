# 이미지 프롬프트 가이드

> donggu 운영 원칙: **본인 자산(강사 사진, 강의장 스크린샷, 작품 이미지)을 로컬에서 `images/`에 직접 박는 방식을 우선**한다. 이 가이드는 진짜로 AI 이미지 생성이 필요할 때만 사용. Claude Code는 네이티브 이미지 생성을 제공하지 않으므로 외부 도구(MCP·외부 API)가 별도로 필요하다.

레이아웃과 이미지 슬롯이 결정된 후에만 프롬프트를 작성한다. 생성된 이미지는 임베드 자산이지 독립 슬라이드가 아니다.

## 하드 룰

- 선택한 이미지 슬롯과 비율을 먼저 맞춘다.
- 액센트 컬러 1개만: International Klein Blue, Lemon Yellow, Lemon Green, Safety Orange 중 하나.
- 베이스라인 유지: 12/16 컬럼 그리드, Helvetica/Inter 느낌, 비대칭, 헤어라인 룰, 직선 사각형, 넉넉한 여백.
- 금지: 그라디언트·그림자·둥근 모서리·글래스·3D·네온·만화풍·가짜 로고·보더·슬라이드 크롬·페이지 번호·푸터·서명·타이틀 바.
- 인포그래픽·UI 텍스트는 덱 언어와 일치.
- 지원 언어: 한국어·영어.
- `21:9` 자산은 주제를 중앙 70% 안전 영역에.
- 같은 페이지 이미지 그룹은 비율·시각 스케일·여백 밀도·라인 굵기 통일.

## 슬롯 비율

| 슬롯 | 비율 | 용도 |
|---|---:|---|
| `s22-hero-21x9` | 21:9 | S22 hero strip |
| `s15-grid-21x9` | 21:9 | S15 이미지 매트릭스 적응 |
| `s15-grid-16x10` | 16:10 | S15 고밀도 UI·인포그래픽 그리드 |
| `s16-brief-21x9` | 21:9 | S16 brief 카드 이미지 행 |
| `s16-brief-16x10` | 16:10 | S16 UI·차트 카드 |

## 다큐멘터리 사진

S22 hero·사례 증거에 사용.

```text
Generate a 21:9 ultra-wide documentary photograph about [page concept]. Style: tightened editorial, high contrast, restrained saturation, real office/city/product-use setting, large negative space, subject centered in the safe middle area. No AI robot, sci-fi interface, staged commercial stock pose, logo, watermark, text, title, footer, page chrome, signature, or border. Output only the core photo.
```

## 시스템·관계 인포그래픽

아키텍처·워크플로우·비교·개념 다이어그램용.

```text
Generate a horizontal International Typographic infographic explaining [concept/process/system relationship]. Use Helvetica/Inter-like sans labels, a strict 12/16-column grid, sharp rectangular modules, 1px hairline rules, black/white/gray, and one [IKB blue / lemon yellow / lemon green / safety orange] accent. Text language: [한국어/English]. Keep each label under 8 words. No gradient, shadow, rounded corner, 3D, cartoon, neon, SaaS template look, logo, title, footer, page number, signature, decorative border, or slide frame. Ratio: [21:9/16:10].
```

## UI 리디자인 자산

스크린샷·대시보드·워크스페이스·코드·제품 흐름용.

```text
Generate a horizontal UI scene that redesigns [screenshot/interface/workspace content] in the tightened layout language. Use a minimal dashboard/workspace structure, sharp panels, hairline rules, 12-column grid, restrained black/white/gray, and one [IKB blue / lemon yellow / lemon green / safety orange] accent. Text language: [한국어/English], short labels only. No real brand logos, gradients, shadows, rounded corners, 3D, neon, title bar, footer, page number, signature, border, or slide chrome. Ratio: 16:10.
```

## 다중 이미지 그리드 자산

S15·S16 그룹에 들어갈 단일 이미지.

```text
Generate one horizontal evidence image about [evidence A/B/C]. It belongs to a coordinated International Typographic image group, so keep the same ratio, element scale, margins, line weight, label density, black/white/gray palette, and single [IKB blue / lemon yellow / lemon green / safety orange] accent as the group. Text language: [한국어/English], short labels only. No title, footer, page number, logo, signature, decorative border, or slide frame. Ratio: [21:9/16:10].
```

## 미니멀 데이터 포스터

수치 증거·작은 차트 자산용.

```text
Generate a horizontal International Typographic data graphic. Core data: [number/comparison/ranking]. Meaning: [explanation]. Use oversized light-weight sans numerals, 1px hairline rules, sharp color blocks, black/white/gray, and one [IKB blue / lemon yellow / lemon green / safety orange] accent. Text language: [한국어/English], only necessary labels. No gradients, shadows, rounded corners, 3D, decorative border, page chrome, title, footer, page number, or signature. Ratio: [16:9/16:10].
```

## 강의 컨텍스트 추가 메모

- 강사·강의장 사진은 생성보다 **본인 실사**를 권장.
- 청중·수강생 사진은 초상권 이슈로 생성보다 stock 또는 자체 촬영 사용.
- 인포그래픽은 사실 `S17 System Diagram`이 HTML·SVG로 더 깔끔하게 처리 가능. 생성 전에 우선 HTML 다이어그램 검토.
- 데이터 포스터는 `S06 KPI Tower`·`S20 Stacked KPI Ledger`가 HTML로 더 정확. 생성 이미지의 숫자는 신뢰하지 말 것.
