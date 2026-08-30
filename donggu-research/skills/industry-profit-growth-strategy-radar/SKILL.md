---
name: industry-profit-growth-strategy-radar
description: "Use when learning industry dynamics and P&L-driven profit pool growth strategy (산업 동향과 이익을 늘리는 사업전략), including value-chain shifts, revenue drivers, pricing and Mix, new markets, recurring revenue, and strategic choices."
version: 1.2.0
author: 강동현 (donggu)
license: MIT
metadata:
  hermes:
    tags: [industry, strategy, pnl, profit-pool, growth, research]
    related_skills: [last30days, k-dart, grounded-citations]
---

# Industry Profit Growth Strategy Radar

## Overview

이 스킬은 산업 뉴스를 많이 읽는 도구가 아니다. **산업 구조와 profit pool의 변화를 읽고, 기업의 P&L에서 이익을 키울 수 있는 사업전략을 반복해서 훈련하는 리서치 시스템**이다.

핵심 흐름:

```text
산업 변화
→ 가치사슬·경쟁구도 변화
→ profit pool 이동
→ 대표 기업 P&L 영향
→ 성장전략 선택지
→ 실행 조건·위험·90일 검증
```

기본 학습 산업은 동구님의 업무와 가장 가까운 **한국 IT서비스·SI·AI 전환 서비스 시장**이다. 사용자가 다른 산업을 지정하면 그 산업으로 한 사이클을 교체한다.

## When to Use

- “산업계 동향을 P&L 관점에서 배우고 싶어”
- “P를 늘리는 사업전략을 공부하고 싶어”
- “profit pool이 어디로 움직이는지 분석해줘”
- “이 기업의 매출 성장과 이익률을 무엇이 만드는지 알고 싶어”
- “AI가 산업 구조와 사업모델을 어떻게 바꾸는지 배우고 싶어”
- recurring cron으로 4주짜리 전략 학습 루프를 돌릴 때

다음에는 쓰지 않는다.

- 일반 AI 뉴스 요약
- 컨설팅펌 사례 모음 자체
- 단일 주식 매수·매도 추천
- 매출·이익 숫자 없이 전략 이름만 나열하는 요청

## Core P&L Model

```text
Profit = Revenue - Cost
Revenue = 고객 수 × 구매 빈도 × 가격·상품 Mix
```

이 스킬은 비용 구조도 보지만 **비용 절감만으로 끝내지 않는다**. Profit의 P를 키우는 주된 성장 옵션은 다음 다섯 가지다.

1. **기존 시장 침투** — 전환율, 점유율, 재구매, 업셀을 높인다.
2. **가격·Mix 개선** — 가격 구조, 패키징, 고마진 상품 비중을 바꾼다.
3. **신규 고객·채널·지역 확장** — 새로운 수요 풀과 유통 경로에 진입한다.
4. **인접 제품·신사업** — 기존 고객·데이터·역량으로 새 매출원을 만든다.
5. **반복 매출화** — 프로젝트형 매출을 운영·구독·플랫폼·성과연동 구조로 전환한다.

각 전략은 반드시 P&L line item과 연결한다. “시장 진출”이 아니라 `신규 고객 수`, `CAC`, `객단가`, `gross margin`, `영업 레버리지`, `회수기간`이 어떻게 변하는지를 쓴다.

## Four-Week Learning Loop

### 1주차 — 산업 구조와 profit pool

한 산업의 구조를 지도로 만든다.

- 고객군과 구매 의사결정자
- 고객이 실제로 돈을 내는 결과
- 가치사슬과 핵심 역할
- 경쟁자·대체재·진입자
- 규제·기술·고객 행동 변화
- 시장 성장률과 별개로 **profit pool**이 어디서 어디로 이동하는가
- bargaining power와 margin이 커지는 지점

산출물:

```text
산업 가치사슬 1장
profit pool 이동 가설 3개
증가/감소하는 사업모델 목록
```

### 2주차 — 기업 P&L과 driver tree

대표 기업 3곳을 고르고 같은 기준으로 비교한다.

필수 지표:

- 매출 성장률
- 매출총이익률
- 영업이익률
- 고객 수
- 객단가
- 구매 빈도
- 가격·상품 Mix
- 반복 매출 비중
- 수주잔고
- 사업부·지역·고객군별 성장
- 영업·인력·기술·인프라 비용

driver tree 예시:

```text
Revenue
├─ 고객 수 = 신규 획득 + 유지 - 이탈
├─ 구매 빈도 / 사용량
└─ 가격·상품 Mix

Operating Profit
├─ Gross Profit
├─ Sales & Marketing
├─ Delivery / Labor
├─ R&D / Platform
└─ G&A
```

산출물: `기업 3개 P&L 비교표 + 성장 driver + margin driver + 확인되지 않은 항목`.

### 3주차 — 실제 성장전략과 결과

기업이 발표한 전략 이름이 아니라 실제 행동과 이후 결과를 추적한다.

- 가격 인상·패키징 변경
- 고마진 상품 Mix 확대
- 버티컬 특화
- 신규 채널·지역 진출
- 파트너십·M&A
- 서비스의 제품화·반복 매출화
- AI 기반 신규 상품
- AI로 delivery 원가·리드타임을 낮춘 사례

각 사례는 다음으로 기록한다.

```text
기회/문제
→ 선택한 전략
→ 실제 실행
→ 필요한 투자·역량
→ P&L driver 변화
→ 이후 실적·KPI
→ 반대 근거·caveat
```

### 4주차 — 1페이지 전략 메모

한 사이클의 결론을 다음 형식으로 작성한다.

```text
산업에서 무엇이 바뀌는가
어디로 profit pool이 이동하는가
우리가 선택할 성장 기회는 무엇인가
P&L의 어떤 항목이 얼마나 바뀌는가
필요한 역량·투자·위험은 무엇인가
90일 검증에서 무엇을 측정할 것인가
```

가능하면 성장 선택지 3개를 `impact × confidence × time-to-value × required capability`로 비교하고 하나를 고른다.

## Research Workflow

### 0. Determine the cycle week

Discord 목적지의 최근 120일 메시지를 읽어 마지막 브리핑의 `week_index`와 산업을 확인한다.

```text
week_index = 1 → 2 → 3 → 4 → 1
```

- 같은 산업은 기본 4주 동안 유지한다.
- 4주차 완료 후 다음 산업 후보를 제안하되 자동 변경하지 않는다.
- 최초 사이클은 `한국 IT서비스·SI·AI 전환 서비스 시장`, week_index 1이다.

### 1. Use last30days for current signal detection

**last30days는 최신 신호 탐지**에 사용한다. 전체 SKILL.md 계약을 따르고 다음을 수행한다.

1. Python 3.12+ interpreter 확정
2. preflight와 source outcome 확인
3. named-entity/industry topic에 대한 query plan JSON 작성
4. 로드된 skill directory의 `last30days.py`를 반드시 `--plan`과 함께 실행
5. 최근 30일의 가격, 제품, 수주, M&A, 파트너십, 고객 행동, 규제, 경영진 발언, 실적 신호 수집

일반 웹검색만으로 last30days 실행을 대체하지 않는다. 실패는 조용한 0건이 아니라 collector failure다.

### 2. Verify structure and numbers from primary sources

last30days 결과는 탐색 seed일 뿐이다. **숫자의 정본**은 다음을 우선한다.

1. DART 사업보고서·분기보고서·재무제표 (`k-dart`의 최신 instruction 사용)
2. 기업 사업보고서·분기 실적·IR 자료
3. earnings call transcript와 경영진 발언
4. 정부·협회 산업통계
5. 가격표, 제품 페이지, 수주·계약, M&A·파트너십 공식 공시
6. 신뢰할 수 있는 시장 데이터
7. 컨설팅 보고서는 구조·가설 보조자료

DART 사용 전 `npx -y @nomadamas/k-skill@0 instruct k-dart`를 실행하고 그 출력 계약을 따른다.

매출총이익률이 공시되지 않거나 서비스 기업의 원가 분류가 다르면 억지로 비교하지 않고 `미공시/비교 제한`으로 표시한다.

### 3. Build a bounded evidence matrix

각 주장마다 다음을 채운다.

```text
claim
driver category
company / industry
metric and period
baseline / change
causal mechanism
source type
canonical URL / filing ID
claim owner
counter-evidence
confidence
```

동시 작업과 citation 충돌을 피하려고 task-scoped `grounded-citations` ledger를 사용한다.

### 4. Distinguish fact, inference, and strategy option

- **Fact:** 공시·실적·가격·수주·정책에서 확인된 내용
- **Inference:** 여러 사실에서 해석한 profit pool 이동 가설
- **Strategy option:** 특정 사업자가 선택할 수 있는 행동

세 문장을 섞지 않는다. 실적 개선과 전략 실행의 인과가 회사 주장뿐이면 그렇게 표시한다.

### 5. Deduplicate by learning identity

최근 120일 메시지와 비교한다.

기본 identity:

```text
industry + driver + strategic mechanism + company evidence
```

새 URL·새 기사만으로 재발행하지 않는다. 다음 중 하나가 있어야 **material learning delta**다.

- 신규 실적·margin·고객·가격·수주 수치
- profit pool 가설을 바꾸는 산업 사건
- 전략 실행의 결과 확인
- 이전 가설의 반례
- 4주차 synthesis를 바꾸는 새 증거

새 학습이 없으면 `[SILENT]`다.

## Weekly Brief Output

Discord 한 메시지, 최대 1,900자. `week_index`에 따라 깊이를 조절하되 아래 공통 형식을 쓴다.

```text
# 산업·P&L 성장전략 학습 · W<week_index>/4

## 이번 주 산업 변화
- 관찰한 사실과 시점

## profit pool 이동
- 어디의 매출·margin이 커지거나 줄어드는지
- 사실과 추론 구분

## P&L driver tree
- Revenue와 Profit의 어떤 driver가 움직이는지

## 성장전략 선택지
1. 선택지
2. 선택지
3. 선택지

## 실제 기업 행동과 결과
- 행동 → P&L 변화 → 확인된 결과·caveat

## 반대 근거와 위험
- 가설을 깨뜨릴 수 있는 증거

## 동구님이 연습할 전략 질문
- 직접 답해볼 질문 1~2개

## Sources
```

4주차에는 `1페이지 전략 메모`를 포함한다. 전략 제안은 대상이 Wishket인지, 특정 기업인지, 가상 사업자인지 명확히 한다. 비공개 회사 정보는 사용하지 않는다.

## Production Cron Contract

```text
schedule: 0 8 * * 1
channel: 📣-산업-P&L-성장전략
skills: [industry-profit-growth-strategy-radar, last30days, k-dart, grounded-citations]
enabled_toolsets: [web, terminal, discord]
```

- Discord `fetch_messages(channel_id, limit=100)`로 최근 120일과 week_index를 읽는다.
- cron prompt에도 last30days 실행, DART/IR 검증, 4주 rotation, learning identity, `[SILENT]`를 명시한다.
- 최초 실운영 run은 scheduler `last_status=ok`, `last_delivery_error=null`, 실제 메시지와 destination을 read-back한다.

## Evidence Rules

- 시장 규모보다 profit pool과 P&L driver를 우선한다.
- 회사 전망과 실제 실적을 구분한다.
- 매출 성장과 이익 성장을 구분한다.
- 수주와 매출 인식을 구분한다.
- 일회성 이익과 반복 가능한 economics를 구분한다.
- 가격 인상과 Mix 개선을 구분한다.
- AI 도입 발표와 실제 매출·원가 효과를 구분한다.
- 서로 다른 회계 분류를 정규화 없이 직접 비교하지 않는다.
- 투자 조언으로 표현하지 않는다.

## Common Pitfalls

1. **트렌드만 정리** — P&L driver와 profit pool 가설까지 내려간다.
2. **비용 절감만 강조** — 매출·가격·Mix·반복 매출 성장 옵션을 반드시 본다.
3. **시장 성장률을 회사 성장으로 간주** — 점유율, 고객군, 사업모델, execution을 분리한다.
4. **전략 이름만 학습** — 실제 행동과 이후 숫자를 추적한다.
5. **공시 숫자 없이 컨설팅 보고서만 사용** — DART·IR·earnings call로 검증한다.
6. **매주 산업을 바꿈** — 같은 산업을 4주 동안 반복해서 구조→P&L→전략→메모로 완결한다.

## Verification Checklist

- [ ] week_index와 현재 산업을 최근 메시지에서 확인했다.
- [ ] last30days.py를 Python 3.12+와 `--plan`으로 실행했다.
- [ ] DART/IR/실적/earnings call/공식 통계로 핵심 숫자를 검증했다.
- [ ] 가치사슬과 profit pool 이동 가설이 있다.
- [ ] 기업 3개 또는 충분한 비교군의 P&L driver를 확인했다.
- [ ] 성장 옵션이 Revenue/Profit line item에 연결된다.
- [ ] 실제 행동 뒤의 결과·반례·caveat를 확인했다.
- [ ] fact, inference, strategy option을 구분했다.
- [ ] 최근 120일 learning identity 중복을 제거했다.
- [ ] 4주차라면 1페이지 전략 메모와 90일 검증이 있다.
- [ ] grounded-citations 검증을 통과했다.
- [ ] 새 학습이 없으면 `[SILENT]`를 반환했다.
