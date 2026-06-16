# donggu-apply

프리랜서 **반자동 지원** 플러그인 — 현재 Wishket(위시켓) 지원(`apply-wishket` 스킬), 다른 플랫폼 확장 가능 구조.

공고 하나에 대해: 로그인 세션 확보 → 공고 브리프·사전질문 크롤 → **포트폴리오 DB**에서 관련 경력 매칭 → 제안서 초안 작성 → 지원 폼 자동입력 → **미리보기 후 사람 승인** → 제출.

핵심 원칙: 제출은 항상 사람이 승인(HITL). 위시켓 채택률은 가격이 아니라 *적합도·성의*에서 갈리고, 완전 자동 제출은 품질을 떨어뜨리고 계정 정지 위험이 있다. 그래서 생성·입력은 자동, **제출만 게이트**.

## 스킬

### `apply-wishket`
- `scripts/wishket_login.py` — 로그인 세션 캡처/점검/자동로그인 (CDP + 영속 프로필, 쿠키 `wsessionid`+`WART`)
- `scripts/wishket_fetch.py` — 공고 상세 + 클라이언트 사전질문 크롤
- `scripts/portfolio_query.py` — portfolio Supabase `projects`에서 스택 매칭 조회 (제안서 SSOT)
- `scripts/wishket_apply_fill.py` — 폼 자동입력. 기본 DRY-RUN, `--submit` 일 때만 제출
- `proposal-template.json` — 답변 스키마

## 전제 (env)

```
SESSIONS_DIR, SCREENSHOTS_DIR
WISHKET_ID, WISHKET_PASSWORD                  # .env, 채팅 노출 금지
PORTFOLIO_SUPABASE_URL=https://ggvlnurppgoroqxbhpej.supabase.co
PORTFOLIO_SUPABASE_KEY                         # projects read 권한
```
Python + `playwright`(chromium). donggu 기준 n8n `api/.venv` 재사용.

## 흐름

```
project URL/ID → 세션확인 → 공고크롤 → 포트폴리오매칭 → 초안작성
              → 폼 자동입력(미리보기) → Discord [✅제출][✏️수정] → 제출
```

자세한 절차는 `skills/apply-wishket/SKILL.md` 참고.
