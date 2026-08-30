---
name: industry-profit-growth-strategy-radar
description: "Use when learning how AI/AX changes real industries and their P&L in beginner-friendly Korean (AX로 산업이 어떻게 바뀌고 이익을 늘리는가), one industry and one company at a time."
version: 1.3.0
author: 강동현 (donggu)
license: MIT
metadata:
  hermes:
    tags: [ax, industry, strategy, pnl, beginner, research]
    related_skills: [last30days, k-dart, grounded-citations]
---

# AX Industry Change & Profit Learning Radar

## Overview

이 스킬의 대상은 AX 솔루션 회사나 SI 회사가 아니다. **AX 공급업체 시장이 아니다.** 제조·금융·유통·물류 같은 실제 산업이 AI 때문에 어떻게 바뀌고, 그 산업의 기업이 돈을 버는 방식과 이익 구조가 어떻게 달라지는지를 배운다.

독자는 **사업전략을 처음 체계적으로 배우는 AI/FDE 실무자**다. 재무·컨설팅 용어를 이미 안다고 가정하지 않는다.

핵심 질문은 하나다.

```text
이 산업은 원래 어떻게 돈을 벌었고,
AI가 고객·업무·비용·상품을 어떻게 바꾸며,
기업은 어떤 선택으로 매출과 이익을 늘릴 수 있는가?
```

## Learning Target

매주 **이번 주 산업 하나**, **기업 하나**, **변화 하나**만 깊게 본다.

산업 순환 기본값:

```text
제조 → 금융 → 유통·커머스 → 물류
→ 헬스케어 → 전문서비스 → 콘텐츠·미디어 → 공공
```

- `industry_index`로 현재 산업을 추적한다.
- 최초 산업은 **제조업**이다.
- 같은 산업을 4주간 학습한 뒤 다음 산업으로 이동한다.
- 특정 산업을 사용자가 요청하면 해당 산업으로 새 4주 사이클을 시작한다.

## Beginner Contract

브리핑은 다음 제한을 지킨다.

- **기업 하나**를 중심으로 설명한다. 비교 회사는 보조로만 쓴다.
- **숫자는 최대 3개**만 본문에 넣는다.
- **새 용어는 최대 3개**만 소개하고 바로 풀어 쓴다.
- 전문용어보다 **초등학생도 이해할 수 있는 한국어**를 먼저 쓴다.
- 영문 용어를 쓸 때는 `한국어 뜻(영문)` 순서로 쓴다.
- 표와 수식보다 실제 돈의 흐름을 이야기로 설명한다.
- 한 문단은 3문장 이내로 유지한다.

좋은 설명 순서:

```text
누가 왜 돈을 내는가
→ 돈이 들어오고 비용이 나가는 흐름
→ AI 전에는 어떻게 일했는가
→ AI 이후에는 무엇이 달라지는가
→ 그래서 어떤 매출 또는 비용 항목이 움직이는가
```

## Simple Money Model

내부 분석은 P&L을 쓰되, 공개 브리핑은 쉬운 말로 번역한다.

```text
Profit = Revenue - Cost
Revenue = 고객 수 × 구매 빈도 × 가격·상품 Mix
```

공개 번역:

- `Revenue` → 회사로 들어오는 돈, 매출
- `Cost` → 상품을 만들고 팔고 운영하는 데 나가는 돈
- `Profit` → 들어온 돈에서 비용을 뺀 뒤 남는 돈, 이익
- `Mix` → 많이 팔리는 상품의 구성
- `profit pool` → 업계 전체 이익이 특히 많이 쌓이는 자리

이익을 늘리는 선택지는 다섯 가지다.

비용 구조도 확인하지만 **비용 절감만으로 끝내지 않는다**. 고객 수·구매 빈도·가격·상품 구성을 바꾸는 매출 성장 선택을 함께 본다.

1. **기존 시장 침투** — 기존 고객이 더 자주, 더 많이 사게 한다.
2. **가격·Mix 개선** — 더 비싸거나 이익이 많이 남는 상품 비중을 키운다.
3. **신규 고객·채널·지역 확장** — 새로운 구매자를 만난다.
4. **인접 제품·신사업** — 기존 역량으로 다른 문제까지 해결한다.
5. **반복 매출화** — 한 번 팔고 끝내지 않고 운영·구독으로 계속 매출을 만든다.

## Four-Week Industry Loop

### 1주차 — 산업 구조와 profit pool

- 고객은 누구인가
- 고객이 무엇에 돈을 내는가
- 가치사슬: 누가 만들고, 팔고, 전달하고, 운영하는가
- AI 전에는 어느 회사가 돈을 많이 벌었는가
- AI 이후에는 업계의 이익이 어디로 이동할 수 있는가

### 2주차 — 기업 P&L과 driver tree

대표 기업 하나의 돈 버는 구조를 본다.

- 매출은 어떤 상품·서비스에서 생기는가
- 매출 성장률은 이전보다 들어오는 돈이 얼마나 늘었는가
- 가장 큰 비용은 무엇인가
- 고객 수, 객단가, 구매 빈도, 가격·상품 Mix 중 무엇이 움직이는가
- 매출총이익률·영업이익률은 쉬운 말로 무엇을 뜻하는가
- 반복 매출·수주잔고가 왜 중요한가

### 3주차 — 실제 성장전략과 결과

기업이 실제로 한 행동 하나를 추적한다.

- 가격 변경
- 새 상품·서비스 출시
- 유통 채널·신규 고객 확대
- AI로 업무 시간·원가 단축
- 일회성 판매를 운영·구독으로 전환

행동 뒤의 숫자나 KPI가 확인되지 않으면 `아직 결과 미확인`이라고 쓴다.

### 4주차 — 1페이지 전략 메모

```text
산업에서 무엇이 바뀌는가
누가 새로 돈을 벌고 누가 어려워지는가
선택 가능한 성장전략은 무엇인가
매출·비용·이익 중 무엇이 움직이는가
필요한 역량과 위험은 무엇인가
90일 검증에서 무엇을 확인할 것인가
```

## Research Workflow

### 0. Determine industry and week

Discord 목적지의 최근 120일 메시지를 읽어 `industry_index`, 산업명, `week_index`를 확인한다.

```text
week_index = 1 → 2 → 3 → 4
industry_index = 0 → 1 → 2 ...
```

- 이전 산업·주차 기록이 없으면 `제조업`, `industry_index=0`, `week_index=1`이다.
- 4주차 다음 실행에서는 위 산업 순환의 다음 항목으로 이동하고 week_index를 1로 되돌린다.
- 과거의 IT서비스·SI·AX 공급기업 브리핑은 새 사이클의 주차로 세지 않는다.

### 1. Detect current AX signals with last30days

**last30days는 최신 신호 탐지**에 실제로 사용한다.

1. Python 3.12+ interpreter를 확정한다.
2. preflight와 source outcome을 확인한다.
3. 현재 산업과 대표 기업을 포함한 query plan JSON을 만든다.
4. 로드된 skill directory의 `last30days.py`를 반드시 `--plan`과 함께 실행한다.
5. 최근 30일의 상품·가격·고객 행동·규제·AI 도입·실적 신호를 수집한다.

일반 웹검색만으로 대체하지 않는다. collector 실패는 그대로 한 줄로 보고한다.

### 2. Verify the business model and three numbers

최신 신호는 다음 **숫자의 정본**으로 확인한다.

1. DART 사업보고서·분기보고서·재무제표
2. 기업 사업보고서·분기 실적·IR 자료
3. earnings call과 공식 제품·가격 페이지
4. 정부·협회 산업통계
5. 고객사 또는 파트너의 공식 사례

DART 사용 전 `npx -y @nomadamas/k-skill@0 instruct k-dart`를 실행한다. `grounded-citations`는 task-scoped ledger로 사용한다.

본문에 넣을 숫자는 최대 3개다. 나머지는 조사 근거로만 사용한다.

### 3. Build the simple causal story

내부 분석표:

```text
산업
대표 기업
누가 돈을 내는가
무엇을 사는가
AI 전에는
AI 이후에는
매출 변화
비용 변화
이익 변화
확인된 숫자
반대 근거
```

최종 브리핑은 `사실 → 쉬운 해석 → 사업전략 선택` 순서로 쓴다. 사실, 추론, 제안을 섞지 않는다.

### 4. Deduplicate by learning identity

```text
industry + customer problem + AI change + money mechanism + company
```

새 기사만으로 다시 보내지 않는다. 신규 실적·가격·고객 행동·규제·전략 결과·반례가 있어야 **material learning delta**다. 새 학습이 없으면 `[SILENT]`다.

## Weekly Brief Output

Discord 한 메시지, 최대 1,600자다.

```text
# AX로 바뀌는 산업 · <산업명> W<week_index>/4

## 이번 주 한 문장
- 어려운 말 없이 결론 하나

## 이 산업은 원래 어떻게 돈을 버나
- 누가 왜 돈을 내는가
- 돈이 들어오고 비용이 나가는 흐름

## AI 때문에 무엇이 바뀌나
- AI 전에는
- AI 이후에는

## 기업 하나로 보기
- 기업의 실제 행동 한 가지

## 숫자 3개만 보기
- 숫자 → 쉬운 뜻

## 용어 3개만 배우기
- 용어: 한 문장 풀이

## 이익을 늘릴 선택지
- 매출을 늘리거나 비용을 낮추는 선택 1~2개

## 동구님이 답해볼 질문
- 직접 생각할 질문 하나

## Sources
```

숫자나 용어가 3개보다 적으면 억지로 채우지 않는다. 출처는 최대 4개다.

## Production Cron Contract

```text
schedule: 0 8 * * 1
channel: 📣-AX-산업변화
skills: [industry-profit-growth-strategy-radar, last30days, k-dart, grounded-citations]
enabled_toolsets: [web, terminal, discord]
```

- `fetch_messages(channel_id, limit=100)`로 최근 120일의 industry_index와 week_index를 읽는다.
- 첫 새 형식 실행은 제조업 W1/4다.
- 실제 실행 후 `last_status=ok`, `last_delivery_error=null`, 목적지 메시지를 read-back한다.

## Common Pitfalls

1. **AX 업체만 분석** — AI를 공급하는 회사가 아니라 AI 때문에 바뀌는 실제 산업을 본다.
2. **용어 사전처럼 설명** — 먼저 돈 버는 이야기를 설명하고 필요한 용어만 나중에 붙인다.
3. **기업 세 곳을 한 번에 비교** — 기업 하나를 중심으로 하고 비교군은 한 문장만 쓴다.
4. **숫자를 많이 넣음** — 의사결정에 필요한 숫자 3개만 남긴다.
5. **AI 도입을 성과로 간주** — 매출·비용·시간·고객 행동 변화가 없으면 결과 미확인이다.
6. **한 번에 산업 전체를 끝내려 함** — 같은 산업을 4주간 반복한다.

## Verification Checklist

- [ ] AX 공급업체가 아니라 AX로 바뀌는 산업을 선택했다.
- [ ] industry_index와 week_index를 확인했다.
- [ ] last30days.py를 Python 3.12+와 `--plan`으로 실행했다.
- [ ] 기업 하나의 돈 버는 구조를 설명했다.
- [ ] AI 전과 AI 이후를 분리했다.
- [ ] 숫자는 최대 3개다.
- [ ] 새 용어는 최대 3개이고 즉시 풀어 썼다.
- [ ] 매출·비용·이익 변화가 쉬운 말로 연결됐다.
- [ ] fact, inference, strategy option을 구분했다.
- [ ] citation을 검증했다.
- [ ] 새 학습이 없으면 `[SILENT]`를 반환했다.
