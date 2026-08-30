---
name: ai-consulting-practice-radar
description: "Use when learning how strategy consulting firms actually do AI/AX work (전략컨설팅펌이 AI 프로젝트에서 실제 하는 일), including problem framing, operating-model redesign, implementation, adoption, and value realization."
version: 1.1.0
author: 강동현 (donggu)
license: MIT
metadata:
  hermes:
    tags: [consulting, ai, ax, practice, learning, research]
    related_skills: [last30days, evidence-first-practitioner-research, grounded-citations]
---

# AI Consulting Practice Radar

## Overview

전략컨설팅펌이 AI를 주제로 무슨 말을 하는지가 아니라, **고객사에서 어떤 문제를 맡고 어떤 산출물과 개입 방식으로 변화를 만드는지**를 매주 학습한다.

이 스킬의 질문은 행사 일정이 아니다.

```text
전략컨설팅펌은 AI 프로젝트에서 실제로 무슨 일을 하는가?
→ 누구의 어떤 문제를 정의하는가?
→ 조직·프로세스·데이터·기술을 어떻게 바꾸는가?
→ 어떤 산출물과 의사결정 구조를 만드는가?
→ PoC에서 production·adoption·ROI까지 어떻게 연결하는가?
→ 그중 무엇을 동구님의 FDE·DA·Wishket AIDP 업무에 옮길 수 있는가?
```

## When to Use

- “전략컨설팅펌이 AI 관련해서 실제로 무슨 일 하는지 배우고 싶어”
- “맥킨지·BCG·베인이 AX 프로젝트를 어떻게 하는지 찾아줘”
- “Big4 AI 컨설팅 방법론과 산출물을 비교해줘”
- “FDE랑 전략컨설턴트의 AI 프로젝트 역할 차이를 알고 싶어”
- recurring cron으로 최신 사례를 매주 공부하고 싶을 때

다음에는 쓰지 않는다.

- 세미나·웨비나 일정만 찾는 요청
- 일반 AI 뉴스 요약
- 컨설팅펌 채용 공고 모음
- 근거 없이 방법론을 만들어 내는 요청

## Research Scope

### Firm set

최소 다음 firm family를 회사별로 확인한다.

- McKinsey / QuantumBlack
- BCG / BCG X
- Bain
- Kearney
- Oliver Wyman
- Roland Berger
- Deloitte / Monitor Deloitte
- EY / EY-Parthenon
- PwC / Strategy&
- KPMG
- Accenture

한 주에 모든 회사를 억지로 넣지는 않는다. 검색은 넓게 하되 브리핑은 **실제 사례·산출물·개입 방식이 확인되는 1~3개 practice signal**만 고른다.

### Practice lens

각 후보를 아래 렌즈로 읽는다.

1. **CEO agenda** — 어떤 성장·비용·리스크·포트폴리오 문제에서 시작했는가
2. **operating model** — 조직, 역할, 의사결정권, human-in-the-loop를 어떻게 재설계했는가
3. **workflow redesign** — 기존 업무를 어떻게 관찰하고 단계·예외·판단 기준을 다시 설계했는가
4. **data and platform** — 데이터 준비도, 지식 기반, 플랫폼, 통합 아키텍처를 어떻게 다뤘는가
5. **governance** — 보안, 책임, 통제, 평가, 모델 리스크를 어떻게 운영체계에 넣었는가
6. **change management** — 현업 참여, 교육, 채택, 역량 이전을 어떻게 만들었는가
7. **value realization** — 생산성·매출·비용·리스크·고객 경험을 어떻게 측정하고 확장했는가

### Delivery stage

사례가 어느 단계까지 증명하는지 분리한다.

```text
문제 정의 → 진단 → 전략·로드맵 → 업무/조직 설계
→ 데이터·기술 구축 → PoC → production
→ adoption → ROI/성과 측정 → 확산·내재화
```

한 단계의 증거를 전체 transformation 성공으로 일반화하지 않는다.

## Workflow

### 0. Run last30days as the mandatory discovery engine

최신 신호 수집은 **`last30days` 스킬을 실제 실행**하는 것으로 시작한다. 이름만 로드하거나 일반 웹검색으로 대체하지 않는다.

1. `last30days` 스킬의 전체 계약을 따른다.
2. Python 3.12+ interpreter를 확정한다.
3. preflight와 source 상태를 확인한다.
4. named-entity topic이므로 reasoning host가 query plan JSON을 만들고 반드시 `--plan`으로 전달한다.
5. 로드된 skill directory의 `scripts/last30days.py`를 실행한다.
6. stdout·저장 결과의 source outcome과 후보 URL을 읽는다.

기본 topic:

```text
How strategy consulting firms actually deliver enterprise AI transformation: client problem framing, workflow and operating model redesign, AI implementation, adoption, governance, capability transfer, and ROI
```

필수 query family:

- firm practices: McKinsey QuantumBlack, BCG X, Bain, Big4, Accenture
- client cases: enterprise AI transformation, production deployment, measurable outcome
- methods: operating model, workflow redesign, transformation office, AI factory, capability building
- practitioner evidence: partner interviews, case leads, engineering blogs, conference talks, podcasts

last30days engine이 실패하면 조용히 일반 웹검색으로 대체하지 않는다. `last30days 조사 실패`를 collector failure로 보고한다.

완료 조건: `last30days.py`가 실제로 실행됐고, query plan에 `--plan`이 사용됐으며, source outcome을 읽었다.

### 1. Expand from discovery to canonical evidence

last30days 결과는 discovery seed다. 최종 주장은 다음 원문에서 검증한다.

우선순위:

1. 고객사가 이름과 결과를 확인한 case study
2. 컨설팅펌의 공식 client case·research·engineering page
3. 해당 프로젝트를 수행한 partner·practitioner의 인터뷰·발표·팟캐스트
4. 공개 산출물, 방법론 그림, transformation framework, GitHub/technical artifact
5. 신뢰할 수 있는 독립 보도

검색 스니펫, 회사 홍보 문구, 행사 소개만으로 “실제 하는 일”을 단정하지 않는다. `grounded-citations` ledger에 retrieval 시점부터 URL을 등록한다.

### 2. Build a claim-level case record

선정 후보마다 아래를 채운다.

```text
firm / practice
client / industry (공개된 경우만)
client problem and accountable executive
starting workflow / operating constraint
consulting work actually performed
artifacts delivered
technology / data role
human roles and governance
implementation stage reached
adoption / capability transfer
measured outcome and who claims it
direct quote / evidence
canonical URL / publication date
evidence level / caveat
```

`consulting work actually performed`에는 동사를 쓴다. 예:

- 진단했다
- 우선순위를 정했다
- target operating model을 설계했다
- workflow와 decision rights를 재설계했다
- 데이터/AI 플랫폼을 구축하거나 기술팀과 공동 구현했다
- transformation office와 governance를 운영했다
- 현업을 교육하고 capability를 이전했다
- KPI와 value tracking을 만들었다

“AI 전략을 지원했다”처럼 검증 불가능한 추상 문장은 제외한다.

### 3. Separate strategy, delivery, and engineering

사례에서 역할을 섞지 않는다.

- **전략컨설팅:** CEO agenda, portfolio/priority, business case, target operating model, governance, transformation steering
- **delivery/implementation consulting:** process redesign, product roadmap, program management, adoption, capability building, value tracking
- **engineering/data:** architecture, data pipelines, models, agents, integration, production operation
- **client ownership:** 도메인 판단, 의사결정, 현업 채택, 지속 운영

회사 이름 때문에 모든 결과를 컨설턴트의 단독 성과로 쓰지 않는다. 파트너·벤더·고객 공동 수행이면 그대로 표시한다.

### 4. Compare with the user's operating model

마지막에는 사례를 동구님의 현재 구조와 비교한다.

- FDE: 기술·구현·현장 산출물
- FDE Lead: PM·delivery·고객 조율
- DA: 문제·성과·도메인 검증
- Wishket AIDP: 고객 AI 도입과 현장 정착

비교 질문:

1. 컨설팅펌이 강하고 현재 체계에 없는 단계는 무엇인가?
2. 이미 FDE/DA가 하고 있지만 이름·산출물·운영 리듬이 없는 것은 무엇인가?
3. 임원 agenda와 현장 구현 사이에 빠진 artifact는 무엇인가?
4. 다음 고객 프로젝트에서 바로 시험할 수 있는 한 가지는 무엇인가?

한 회사 사례의 산출물을 보편적 best practice로 일반화하지 않는다. **출처를 일반화하지 않는다.**

### 5. Deduplicate by learning, not URL

최근 목적지 메시지에서 최근 90일 브리핑을 읽는다.

- 동일 case/client/firm만 막지 않는다.
- 동일한 핵심 교훈과 동일 artifact를 반복하면 제외한다.
- 새 URL이어도 교훈이 같으면 중복이다.
- 같은 사례라도 신규 성과 수치, production 전환, governance 변화, capability transfer가 공개되면 material learning delta다.

기본 learning identity:

```text
firm + client/problem + intervention + artifact/outcome
```

날짜·수치·단계는 mutable fields로 비교한다. identity 자체에 넣어 업데이트를 새 사례로 오인하지 않는다.

### 6. Produce one weekly learning brief

공개 결과는 최대 1,800자, 사례 1~3개다. 기사 모음이 아니라 하나의 학습 브리핑으로 통합한다.

```text
# 이번 주 AI 전략컨설팅 실무 브리핑

## 이번 주 핵심 판단
- 컨설팅펌이 AI 프로젝트에서 실제로 하는 일을 한 문장으로 요약

## 컨설팅펌이 실제로 한 일
1. Firm · client/problem
   - 한 일: 구체적 동사와 개입
   - 근거/결과: 검증된 단계·수치·caveat
   - canonical URL

## 산출물과 개입 방식
- 이번 주 반복해서 보인 artifact 2~4개

## 동구님 업무와 비교
- FDE / FDE Lead / DA / Wishket AIDP에서 이미 하는 것
- 추가할 만한 빈칸

## 이번 주 따라 해볼 것
- 다음 고객 업무에서 30~90분 안에 시험 가능한 한 가지

## 더 파볼 질문
- 다음 주 조사 질문 한 개
```

사실 문장은 inline citation을 붙이고 Sources 블록은 ledger에서 렌더한다. 단, Discord 가독성을 위해 Sources는 최대 5개다.

### 7. Bind the production cron explicitly

권장 production contract:

```text
schedule: 0 8 * * 1        # 매주 월요일 08:00 KST
deliver: discord:<dedicated-channel-id>
skills: [ai-consulting-practice-radar, last30days, evidence-first-practitioner-research, grounded-citations]
enabled_toolsets: [web, terminal, discord]
workdir: <stable existing directory>
```

- dedicated channel은 `🧠-AI-전략컨설팅-리서치`를 쓴다.
- cron prompt에 정확한 channel ID를 넣는다.
- Discord `fetch_messages(channel_id, limit=100)`로 최근 90일 학습 이력을 읽는다.
- `last30days.py` 실행, `--plan`, canonical evidence, learning identity, output sections를 prompt에도 명시한다.
- 새 사례 또는 **material learning delta**가 없으면 정확히 `[SILENT]`를 반환한다.
- 첫 production run은 실제 실행하고 scheduler의 `last_status=ok`, `last_delivery_error=null`, destination channel ID, 실제 메시지를 read-back한다.

## Evidence Rules

- 고객명과 성과 수치는 주장 주체를 표시한다.
- 회사-authored case는 당사자 주장이지 독립 검증이 아니다.
- pilot·PoC는 production으로 부르지 않는다.
- production은 adoption·성과와 동일하지 않다.
- 기술 구축이 없는 전략 프로젝트와 엔지니어링 공동 수행을 구분한다.
- 컨설팅펌의 framework 소개를 고객 현장 수행 증거로 승격하지 않는다.
- 기사 날짜와 사례 발생 날짜를 구분한다.
- 비공개 고객·프로젝트 경험을 공개 사례와 섞지 않는다.

## Common Pitfalls

1. **행사와 세미나만 수집**
   행사 자체가 아니라 발표 속 client problem, intervention, artifact, outcome을 추출한다.

2. **회사 마케팅 문구를 수행 사실로 사용**
   구체적 동사·산출물·단계·결과가 확인되지 않으면 제외한다.

3. **전략과 구현을 한 덩어리로 설명**
   strategy, delivery, engineering, client ownership을 분리한다.

4. **컨설팅 framework를 정답처럼 복사**
   현재 FDE/DA 체계와 비교해 빈칸과 실험만 가져온다.

5. **매주 같은 AI transformation 결론 반복**
   learning identity로 중복을 막고 material learning delta만 재발행한다.

6. **과도한 회사 수와 기사 수**
   넓게 조사하되 학습 가치가 큰 사례 1~3개만 남긴다.

## Verification Checklist

- [ ] last30days engine을 Python 3.12+와 `--plan`으로 실제 실행했다.
- [ ] source outcome과 coverage failure를 확인했다.
- [ ] firm set을 넓게 검색했다.
- [ ] 각 사례에 client problem, intervention, artifact, stage, outcome, caveat가 있다.
- [ ] strategy, delivery, engineering, client ownership을 구분했다.
- [ ] PoC, production, adoption, ROI를 혼동하지 않았다.
- [ ] learning identity와 최근 90일 이력으로 중복을 제거했다.
- [ ] FDE / FDE Lead / DA / Wishket AIDP 비교가 있다.
- [ ] 이번 주 따라 해볼 것이 작고 구체적이다.
- [ ] grounded-citations 검증을 통과했다.
- [ ] cron이면 새 학습이 없을 때 `[SILENT]`를 반환했다.
- [ ] 신청·발행·외부 mutation을 하지 않았다.
