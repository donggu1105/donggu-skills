---
name: apply-wishket
description: Use when applying to a Wishket (위시켓) freelance project — drafting or submitting a 제안서/지원서 for a wishket.com/project/<id> URL or project ID. Triggers include "위시켓 지원", "위시켓 제안서", "wishket apply", "이 공고 지원해줘", a wishket.com/project/<id>/ link, or a strong_apply alert from the project-feed pipeline.
---

# apply-wishket

Semi-automated Wishket proposal pipeline. The agent does the work; **the human keeps the quality gate** — a proposal is only submitted after explicit approval (Discord button or "제출" reply).

> Built for donggu's stack: portfolio data lives in the `portfolio-supabase` DB (project-ref `ggvlnurppgoroqxbhpej`); browser automation reuses the n8n publishing stack's Playwright + persistent session pattern.

## Core principle — HITL before submit

Wishket proposal acceptance hinges on **fit and sincerity**, not low price. Fully automatic submission flattens quality and risks account suspension. So: generate + autofill automatically, **preview, then submit only on approval**. `wishket_apply_fill.py` is DRY-RUN by default; it submits only with `--submit`.

## Prerequisites (env)

```
SESSIONS_DIR=<dir>                 # holds wishket-storage.json (login session)
SCREENSHOTS_DIR=<dir>              # preview screenshots
WISHKET_ID, WISHKET_PASSWORD      # for auto-login (from .env, never chat)
PORTFOLIO_SUPABASE_URL=https://ggvlnurppgoroqxbhpej.supabase.co
PORTFOLIO_SUPABASE_KEY=<anon-or-service key with projects read>
```
Python with `playwright` + chromium (donggu: `/Users/joeykang/workspace/projects/n8n/api/.venv/bin/python`).
Use **absolute** `SESSIONS_DIR`/`SCREENSHOTS_DIR` — agent cwd resets between calls, so the scripts' `./sessions` default is unreliable. Creds come from `WISHKET_ID`/`WISHKET_PASSWORD` env, or a `WISHKET_CRED_FILE` (`.env`-style; file-first to avoid ps/env exposure).

## Flow

```
project URL/ID
  → 1. ensure session   (wishket_login.py; auto-login if wishket-storage.json missing/expired)
  → 2. crawl brief      (wishket_fetch.py → title, description, pre_questions)
  → 3. pull portfolio   (portfolio_query.py --tags <stack from brief>)
  → 4. draft answers    (agent writes proposal JSON — see "Drafting" below)
  → 5. autofill preview (wishket_apply_fill.py <id> answers.json → screenshot, NO submit)
  → 6. HITL approve     (Discord buttons [✅ 제출] [✏️ 수정])
  → 7. submit           (wishket_apply_fill.py <id> answers.json --submit)
```

## Steps

### 1. Session
Consumer scripts read `SESSIONS_DIR/wishket-storage.json` (Playwright storage_state). Bootstrap it once, reuse until expiry.
```
python scripts/wishket_login.py launch &      # 1. headed browser + CDP port — REQUIRED before probe/autologin
python scripts/wishket_login.py autologin      # 2. fills WISHKET_ID/PASSWORD, clicks 로그인
python scripts/wishket_login.py probe          # 3. optional: prints LOGGED_IN + cookies
```
On success (`wsessionid` + `WART` cookies) both `launch` and `autologin` **write `wishket-storage.json`** — that snapshot is what `fetch`/`fill` reuse. `_fwb` bot-detection can block headless auto-login, so a one-time **headed** login is the reliable path; re-bootstrap when the session expires. Captcha/locked account → log in by hand in the `launch` window.

### 2. Crawl the brief
```
python scripts/wishket_fetch.py <project_id>
```
Returns `{title, description, pre_questions[]}`. The description carries required stack, budget, schedule; pre_questions are the client's "* " questions on the apply page.

### 3. Pull matching portfolio
```
python scripts/portfolio_query.py --tags "Next.js,Supabase,React,AI" --limit 6
```
Reads the `projects` table (slug, title, summary, role, problem, solution, impact_summary, tags, features — all i18n ko/en), ranks by stack overlap with the brief. This is the **single source of truth** for experience — do not invent or hand-copy; cite only what the DB returns.

### 4. Drafting the proposal (agent task, not a script)

**First read `wishket-proposal-playbook.md`** — the research-backed 5-part body structure (project analysis → proposal → similar experience w/ verifiable URLs → budget rationale → trust close), pre-question answer patterns, and budget/term conventions (VAT-excluded amount, calendar days). Apply it.

Produce `answers.json` (see `proposal-template.json`). Rules:
- **Truthfulness**: every claim must trace to a `projects` row from step 3 or the resume. Respect the portfolio's honesty rules (team vs solo ownership).
- **Fit over price**: lead with concrete launched work + a phased plan that matches the brief's schedule/scope. Don't undercut on budget/term to win.
- **Pre-questions**: answer each in the client's order; URL questions → real launched links from the DB; experience questions → specific projects with metrics.
- **Body (`body`)**: greeting → stack match → 2-3 reasons (mapped to portfolio) → portfolio link → close.
- `budget`/`term` are the human's call — set a sensible default and flag it for review.

### 5. Preview (no submit)
```
python scripts/wishket_apply_fill.py <project_id> answers.json
```
Fills budget/term/start, the pre-question answers, body, and related-career = "none". Saves `wishket_apply_filled.png`. Send it to Discord for review.

> ⚠️ **Known limitation:** resume selection and non-"none" related-career are NOT yet automated (the apply form uses custom card/modal widgets, not plain inputs). Wishket requires a selected resume to enable the submit button, so until `wishket_apply_fill.py` is extended, select the resume (and any related career) **by hand in the browser** at submit time. Otherwise `--submit` may find the submit button disabled and time out.
>
> **Verify, don't trust the print:** `fetch` and `fill` swallow selector failures silently (`try/except`), so a `FILLED_SHOT`/success line does NOT mean every field populated. Always eyeball `wishket_apply_filled.png` to confirm budget/term/answers/body are actually filled, and sanity-check `fetch` output (`description` not `"(... failed)"`, `pre_questions` non-empty and aligned) before drafting.

### 6 & 7. Approve → submit
Present Discord buttons via the `message` tool `presentation` (callback actions route back to the agent):
- `[✅ 제출]` → `wishket_apply_fill.py <id> answers.json --submit`
- `[✏️ 수정]` → revise `answers.json`, re-preview

Submission is irreversible — never pass `--submit` without explicit human approval.

## Files
- `scripts/wishket_login.py` — session capture/probe/autologin (CDP + persistent profile)
- `scripts/wishket_fetch.py` — project brief + pre-question crawler
- `scripts/portfolio_query.py` — portfolio Supabase projects query (stack-matched)
- `scripts/wishket_apply_fill.py` — form autofill; DRY-RUN unless `--submit`
- `proposal-template.json` — answer schema
- `wishket-proposal-playbook.md` — research-backed proposal tactics; read before drafting (step 4)
