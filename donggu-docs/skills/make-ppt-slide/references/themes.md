# 컬러 테마 프리셋

덱당 액센트 컬러는 **1개만**. 두 액센트 섞기 금지. 임의 hex 사용 금지.

## 적용 방법

1. `assets/template.html` 열기.
2. `:root` 블록 찾기.
3. 테마 변수 그룹을 그대로 교체.
4. spacing·type·motion 토큰은 건드리지 않는다.

## International Klein Blue (기본)

범용. AI 제품, 강의, 디자인 시스템, 분석 토크에 적합. **donggu 강의 덱 기본값**.

```css
--paper:#fafaf8;
--paper-rgb:250,250,248;
--ink:#0a0a0a;
--ink-rgb:10,10,10;
--grey-1:#f0f0ee;
--grey-2:#d4d4d2;
--grey-3:#737373;
--accent:#002FA7;
--accent-rgb:0,47,167;
--accent-on:#ffffff;
--accent-bright:#5B7BFF;
```

## Lemon Yellow

청년·스포츠·소비재·레트로 테마.

```css
--paper:#fafaf8;
--paper-rgb:250,250,248;
--ink:#0a0a0a;
--ink-rgb:10,10,10;
--grey-1:#f0f0ee;
--grey-2:#d4d4d2;
--grey-3:#737373;
--accent:#FFD500;
--accent-rgb:255,213,0;
--accent-on:#0a0a0a;
--accent-bright:#FFE866;
```

## Lemon Green

지속가능성·건강·미래기술.

```css
--paper:#fafaf8;
--paper-rgb:250,250,248;
--ink:#0a0a0a;
--ink-rgb:10,10,10;
--grey-1:#f0f0ee;
--grey-2:#d4d4d2;
--grey-3:#737373;
--accent:#C5E803;
--accent-rgb:197,232,3;
--accent-on:#0a0a0a;
--accent-bright:#DBFF2F;
```

## Safety Orange

산업 토픽·경고·결정 포인트·런칭.

```css
--paper:#fafaf8;
--paper-rgb:250,250,248;
--ink:#0a0a0a;
--ink-rgb:10,10,10;
--grey-1:#f0f0ee;
--grey-2:#d4d4d2;
--grey-3:#737373;
--accent:#FF6B35;
--accent-rgb:255,107,53;
--accent-on:#ffffff;
--accent-bright:#FF8A5F;
```

## 선택 가이드

| 용도 | 테마 |
|---|---|
| 기본·강의·AI·테크·디자인·제품 런칭 | International Klein Blue |
| 청년·스포츠·소비재 에너지 | Lemon Yellow |
| 지속가능성·건강·미래기술 | Lemon Green |
| 산업·경고·결정·긴급 | Safety Orange |

## 금지 사항

- 두 액센트 컬러 혼용 금지.
- 그레이 스케일 변수 변경 금지.
- 그라디언트·그림자·투명 효과·둥근 액센트 블록 금지.
