"""저장된 위시켓 세션으로 지원 폼을 답변 JSON으로 채운다.

기본은 DRY RUN — 폼을 채우고 미리보기 스크린샷만 남긴다(제출하지 않음).
--submit 플래그가 있을 때만 "제출하기"를 클릭한다.

usage:
  python scripts/wishket_apply_fill.py <project_id> <answers.json> [--submit]
env: SESSIONS_DIR, SCREENSHOTS_DIR
세션 파일: <SESSIONS_DIR>/wishket-storage.json (wishket_login.py로 생성)
"""

import os
import sys
import json

from playwright.sync_api import sync_playwright

SESSIONS = os.environ.get("SESSIONS_DIR", "./sessions")
SHOTS = os.environ.get("SCREENSHOTS_DIR", "./screenshots")
STATE = os.path.join(SESSIONS, "wishket-storage.json")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def main(pid: str, ans_path: str, submit: bool = False):
    with open(ans_path, encoding="utf-8") as f:
        ans = json.load(f)
    url = f"https://www.wishket.com/project/{pid}/proposal/apply/"
    os.makedirs(SHOTS, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(storage_state=STATE, locale="ko-KR", user_agent=UA)
        pg = ctx.new_page()
        pg.set_default_timeout(30000)
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(2000)
        if "/accounts/login" in pg.url or "auth.wishket.com" in pg.url:
            print("SESSION_EXPIRED — re-run wishket_login.py autologin")
            br.close()
            return

        # 금액 / 기간
        if ans.get("budget"):
            pg.fill("input[name=budget]", str(ans["budget"]))
        if ans.get("term"):
            pg.fill("input[name=term]", str(ans["term"]))
        tt = ans.get("term_type")
        if tt == "month":
            try: pg.check("#term_type_month")
            except Exception: pass
        elif tt == "day":
            try: pg.check("#term_type_day")
            except Exception: pass
        if ans.get("start_immediate"):
            try: pg.check("#progress_immediate")
            except Exception: pass

        # 사전질문 답변(순서대로)
        qs = pg.locator("textarea[name=pre_question_answer]")
        for i, a in enumerate(ans.get("pre_question_answers", [])):
            try:
                qs.nth(i).fill(a)
            except Exception as e:
                print(f"Q{i} fill err: {e}")

        # 지원 내용 본문
        if ans.get("body"):
            try:
                pg.fill("#apply_body", ans["body"])
            except Exception as e:
                print(f"body fill err: {e}")

        # 관련 경력
        if ans.get("related_employment") == "none":
            try: pg.check("#has_not_related_employment")
            except Exception: pass

        pg.wait_for_timeout(800)
        shot = os.path.join(SHOTS, "wishket_apply_filled.png")
        pg.screenshot(path=shot, full_page=True)
        print("FILLED_SHOT", shot)

        if submit:
            print("SUBMIT requested — clicking 제출하기")
            try:
                pg.get_by_role("button", name="제출하기").click()
                pg.wait_for_timeout(3000)
                print("AFTER_SUBMIT_URL", pg.url)
                pg.screenshot(path=os.path.join(SHOTS, "wishket_after_submit.png"), full_page=True)
            except Exception as e:
                print(f"submit err: {e}")
        else:
            print("DRY_RUN — 제출하지 않음(미리보기만)")
        br.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: wishket_apply_fill.py <pid> <answers.json> [--submit]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], "--submit" in sys.argv)
