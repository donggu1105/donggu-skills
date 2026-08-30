---
name: consulting-event-radar
description: "Use when finding upcoming strategy consulting, Big4, or professional-services seminars, recruiting events, webinars, and executive forums in Korea. Verifies live registration and recommends only events worth the user's time."
version: 1.0.0
author: 강동현 (donggu)
license: MIT
metadata:
  hermes:
    tags: [consulting, events, seminars, korea, research]
    related_skills: [last30days, grounded-citations]
---

# Consulting Event Radar

## Overview

한국에서 열리는 **전략컨설팅펌·Big4·전문서비스사의 공개 행사**를 찾아, 지금 신청할 수 있고 실제로 갈 가치가 있는 것만 추천한다. 단순 행사 검색이 아니라 `직접 주최 여부`, `사용자 적합도`, `신청 가능 상태`, `일정·장소·비용`을 원문으로 검증하는 리서치 절차다.

MBB 채용행사만 찾지 않는다. 전략·AX·AI·기업 운영모델·산업전략을 다루는 Big4 및 인접 CxO 포럼까지 검색하되, 결과에서는 **컨설팅펌 직접 주최**와 **인접 행사**를 분리한다.

## When to Use

- “전략컨설팅펌 세미나 같은 거 없나”
- “맥킨지·BCG·베인 행사 찾아줘”
- “이번 달 컨설팅/AX 세미나 뭐 갈 만해?”
- “Big4 웨비나나 경영전략 포럼 알려줘”
- recurring cron으로 새로운 행사만 주기적으로 감시할 때

다음에는 쓰지 않는다.

- 과거 행사 자료만 찾는 요청
- 일반 개발자 밋업·교육과정 검색
- 사용자를 대신한 참가 신청·결제·캘린더 등록. 이들은 별도 외부 행동이며 명시 승인이 필요하다.

## Search Scope

### 1. Tier A — 전략컨설팅펌 직접 행사

우선 검색한다.

- McKinsey & Company / QuantumBlack
- BCG / BCG X
- Bain & Company
- Kearney
- Oliver Wyman
- Roland Berger
- Strategy&
- EY-Parthenon
- Monitor Deloitte

행사 유형:

- 공개 세미나·웨비나·컨퍼런스
- recruiting event·career session·case workshop
- 산업·기능별 executive briefing
- 보고서 발표 세션과 고객 공개 포럼

### 2. Tier B — Big4·전문서비스사 직접 행사

- Deloitte Korea
- EY Korea
- PwC Korea / 삼일PwC
- KPMG Korea / 삼정KPMG
- Accenture Korea 및 동급 전문서비스사

전략, AI/AX, 운영모델, 조직·인재, M&A, 산업전환처럼 컨설팅 인사이트를 얻을 수 있는 행사만 포함한다. 세무·회계 규정 설명만 있는 행사는 사용자 맥락과 직접 연결될 때만 남긴다.

### 3. Tier C — 인접 행사

컨설팅펌 주최가 없어도 다음 조건을 모두 충족하면 보충할 수 있다.

- 기업 전략·AX·AI 운영·산업 혁신을 다룬다.
- 공식 주최 페이지가 있다.
- 실제 기업 리더·컨설팅 파트너·정책 담당자가 발표한다.
- 사용자가 현장 FDE/AX 관점이나 네트워킹 가치를 얻을 수 있다.

Tier C를 Tier A처럼 포장하지 않는다. 반드시 `인접 행사`라고 표시한다.

## Workflow

### 0. Run last30days as the discovery engine

이 스킬의 최신 신호 수집은 **`last30days` 스킬을 실제로 실행**하는 것에서 시작한다. 이름만 첨부하거나 일반 `web_search`로 흉내 내지 않는다.

1. `last30days` 스킬을 로드하고 그 계약을 우선한다.
2. 스킬이 요구하는 Python 3.12+ interpreter, preflight, query plan, engine invocation을 따른다.
3. 기본 topic은 다음 의도를 포함한다.

```text
South Korea strategy consulting Big4 professional services seminars webinars recruiting events executive forums AI AX enterprise operating model
```

4. last30days 결과는 **discovery seed**다. 소셜·커뮤니티 언급량과 최근 발견 URL은 후보 탐색에 쓰되, 행사 날짜·신청 상태·비용·자격은 아래 공식 원문 검증 단계가 소유한다.
5. last30days engine이 실패하면 일반 웹검색만으로 조용히 대체하지 않는다. `last30days 조사 실패`를 collector failure로 분리해 운영 오류로 보고한다.

완료 조건: `last30days.py`가 실제로 한 번 이상 실행됐고, 저장된 결과 또는 stdout에서 후보 URL과 source outcome을 읽었다.

### 1. Fix the time boundary

먼저 도구로 **current KST** 시각을 확인한다. 모든 행사 날짜와 마감은 이 시각을 기준으로 판정한다.

기본 탐색 창:

- 대화형 요청: 오늘부터 **45 days**
- 주간 cron: 오늘부터 **45 days**, 지난 실행 이후 새로 발견됐거나 materially updated된 행사

사용자가 월·기간을 지정하면 그 범위를 우선한다.

완료 조건: 검색 시작 시각과 미래 행사 창이 명시돼 있다.

### 2. Search broad, then official

한 번의 한국어 검색으로 끝내지 않는다. 아래 query family를 조합한다.

- 회사명 + 세미나 / 웨비나 / 컨퍼런스 / 포럼 / 설명회
- 회사명 + event / webinar / conference / recruiting event + Korea / Seoul
- `site:<official-domain>` + 연도·월 + event 키워드
- 공식 careers/events 페이지
- 한국 페이지가 약하면 글로벌 events 페이지에서 Korea/Seoul/virtual 필터
- 보조 검색: 온오프믹스, 행사 미디어, 대학 채용 게시판. 단, 원문 발견용 seed로만 사용한다.

동일 회사라도 insight event와 recruiting event를 별도로 검색한다.

완료 조건: Tier A와 Tier B의 핵심 회사가 각각 검색됐고, 공식 event hub가 있는 회사는 hub까지 확인했다.

### 3. Verify every candidate at the official source

**search snippet만으로 추천하지 않는다.** 후보마다 official source 또는 공식 등록 페이지를 열어 다음을 확인한다.

- 정확한 행사명
- 주최사와 공동주최사
- 일시와 timezone
- 장소 또는 online 여부
- 대상·참가 자격
- 비용
- 신청 마감
- **registration status**: open / invite-only / waitlist / closed / full / cancelled / unclear
- 신청 또는 상세 페이지의 **canonical URL**
- 프로그램과 주요 연사

공식 원문이 없고 제3자 게시물만 있으면 `확인 필요`로 낮추며 추천 1순위로 올리지 않는다. 검색 결과 날짜와 페이지 본문 날짜가 다르면 본문·등록 페이지를 우선한다.

완료 조건: 공개 추천에 들어가는 모든 행사의 날짜·상태·URL이 원문으로 확인됐다.

### 4. Normalize and deduplicate

콘텐츠 URL, 등록 URL, 보도자료가 달라도 **event identity**가 같으면 하나로 묶는다.

기본 event key:

```text
actor + event + date + location/mode
```

다음은 material update다.

- 신청 시작·마감·조기마감
- 장소·시간 변경
- 신규 연사·프로그램 공개
- online/offline 전환
- 행사 취소

material update가 아니면 같은 행사를 새 항목처럼 반복하지 않는다.

### 5. Rank for this user

각 후보를 다음 순서로 평가한다.

1. **사용자 적합도**
   - FDE/AX 현장 적용
   - AI가 조직·프로세스·운영모델을 바꾸는 사례
   - 전략 수립보다 실행·정착·성과까지 다루는가
   - 실제 고객·기업 사례와 의사결정자가 있는가
2. **주최 신뢰도**
   - Tier A > Tier B > Tier C
3. **참가 가능성**
   - open > 선별 승인 > waitlist > invite-only/unclear
4. **정보 밀도와 네트워킹 가치**
5. **비용·시간 대비 가치**

채용 준비가 목적이 아닌 사용자의 경우, 학생 한정 case workshop보다 기업 전략·AI/AX 실행 세미나를 우선한다. 다만 MBB가 공개 career session을 열었으면 별도 항목으로 알린다.

### 6. Write grounded output

외부 사실을 사용하므로 `grounded-citations` 절차를 적용한다. 출처 URL을 retrieval 시점에 ledger에 등록하고, 행사별 핵심 사실 문장에 inline citation을 붙인다. 마지막 Sources 블록은 ledger에서 렌더한다.

#### 대화형 기본 형식

```text
있습니다. 제가 고르면 <추천 1순위>입니다.

### 추천 1순위
- 행사명
- 일시·장소
- 왜 동구님에게 맞는지
- 비용·신청 상태
- URL

### 컨설팅펌 직접 주최
- 최대 3건

### 인접 행사
- 최대 2건

### 현재 확인되지 않은 곳
- 예: MBB 한국 공개 행사 미확인. 공식 event hub 링크 제공.

## Sources
...
```

`현재 확인되지 않은 곳`은 실제 공식 페이지까지 확인한 경우에만 쓴다. “없다”가 아니라 “현재 공개·신청 가능한 행사를 확인하지 못했다”라고 정확히 표현한다.

#### cron 기본 형식

- 새 행사 또는 material update가 없으면 최종 응답은 정확히 `[SILENT]`.
- 있으면 `이번 주 새로 확인된 컨설팅·AX 행사` 제목 아래 최대 5건만 전달한다.
- 각 항목: `행사명 — 날짜·장소 — 추천 이유 한 문장 — 신청 상태 — canonical URL`.
- 내부 검색 로그·점수·탈락 후보·Sources ledger 운영 과정은 공개 메시지에 노출하지 않는다.
- 오류나 공식 원문 검증 실패를 0건으로 가장하지 않는다. 필요한 경우 짧은 운영 오류를 보고한다.

### 7. Suppress recurring duplicates

cron에서는 발송 전 **최근 목적지 메시지**를 읽고 최근 60일간 보낸 event key와 canonical URL을 추출한다.

- 같은 event key는 다시 보내지 않는다.
- material update일 때만 `업데이트`로 다시 보낸다.
- 단순 보도자료 추가, URL 파라미터 변경, 재전재는 업데이트가 아니다.
- 목적지 기록을 읽지 못하면 exact URL 중복만으로 안전하다고 간주하지 말고 degraded 상태를 명시한다.

완료 조건: 새 이벤트와 material update만 남아 있다.

### 8. Bind the production cron explicitly

이 스킬은 범용 절차이고, 실제 스케줄·대상 채널은 Hermes cron job이 소유한다. 생산 설정은 암묵적으로 추측하지 않는다.

권장 production contract:

```text
schedule: 0 8 * * 1        # 매주 월요일 08:00 KST
deliver: discord:<dedicated-channel-id>
skills: [consulting-event-radar, last30days, grounded-citations]
enabled_toolsets: [web, terminal, discord]
workdir: <stable existing directory>
```

- dedicated channel은 `📣-컨설팅-행사-레이더`처럼 목적이 드러나는 이름을 쓴다.
- cron prompt에 정확한 `channel_id`를 넣고 Discord `fetch_messages(channel_id, limit=100)`로 최근 이력을 읽는다.
- `last30days.py`를 실제 실행했다는 완료 조건, 공식 원문 검증, event identity, `[SILENT]` 조건을 cron prompt에도 반복한다.
- 첫 production run은 명시적으로 실행하고, scheduler의 `last_status=ok`, `last_delivery_error=null`, 실제 채널 메시지와 정확한 destination ID를 read-back한다.
- 테스트 때문에 일반 대화 thread에 임시로 발송했다면 잘못된 테스트 메시지를 삭제하고 dedicated channel을 정본으로 다시 연결한다.
- 사용자가 다른 주기나 목적지를 지정하면 이 기본값보다 최신 명시 요청이 우선한다.

완료 조건: cron registry의 schedule·skills·toolsets·delivery·workdir가 의도와 정확히 일치하고, 한 번의 실제 실행이 dedicated channel에서 검증됐다.

## Evidence Rules

- 공식 회사 event/careers 페이지가 최우선이다.
- 공식 등록 폼이 상세 페이지보다 최신이면 등록 상태는 폼을 따른다.
- 대학·커뮤니티 재게시물은 공식 페이지가 검색되지 않을 때 discovery seed로만 쓴다.
- 날짜가 지난 페이지, replay-only 페이지, 자료 신청 페이지는 upcoming event로 세지 않는다.
- 신청 페이지가 열리더라도 행사 날짜가 지났으면 제외한다.
- `closed`, `full`, `cancelled`는 추천 목록에서 제외하고, 매우 중요한 행사 업데이트일 때만 상태 알림으로 언급한다.
- invite-only 대상이 사용자와 맞지 않으면 제외한다.
- 비용이나 대상이 불명확하면 추측하지 않는다.

## Common Pitfalls

1. **검색 스니펫의 미래 날짜를 그대로 믿음**
   페이지 본문·등록 폼에서 날짜와 신청 상태를 재검증한다.

2. **MBB 행사만 찾고 “없다”고 결론**
   Tier B와 Tier C까지 확장하되 결과 레이블은 분리한다.

3. **과거 행사 자료 신청을 현재 행사로 추천**
   event date와 registration status를 각각 검사한다.

4. **채용 이벤트와 비즈니스 세미나를 섞음**
   목적과 대상 자격을 명시하고 사용자의 현재 역할에 맞춰 순위를 정한다.

5. **cron이 매주 같은 행사를 재발송**
   canonical URL이 아니라 event identity와 최근 목적지 이력을 함께 사용한다.

6. **행사 신청까지 자동 실행**
   이 스킬은 검색·검증·추천까지만 한다. 신청·결제·캘린더 등록은 사용자 승인 뒤 별도 수행한다.

## Verification Checklist

- [ ] `last30days` 스킬 계약에 따라 `last30days.py`를 실제 실행했고 source outcome을 확인했다.
- [ ] current KST와 탐색 기간을 도구로 확인했다.
- [ ] Tier A·Tier B 핵심 회사를 회사별로 검색했다.
- [ ] 추천 행사마다 official source를 읽었다.
- [ ] 날짜, timezone, 장소, 대상, 비용, 마감, registration status를 확인했다.
- [ ] closed/full/cancelled/과거 행사를 추천에서 제외했다.
- [ ] event identity 기준으로 중복을 제거했다.
- [ ] 컨설팅펌 직접 주최와 인접 행사를 분리했다.
- [ ] 사용자 적합도 기준으로 추천 1순위를 하나 골랐다.
- [ ] grounded-citations ledger에서 인용과 Sources 블록을 만들었다.
- [ ] cron이면 최근 목적지 메시지와 비교했고, 새 항목이 없으면 `[SILENT]`를 반환했다.
- [ ] 신청·결제·캘린더 등록 같은 외부 행동을 하지 않았다.
