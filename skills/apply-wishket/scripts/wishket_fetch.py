"""위시켓 공고 상세 + 클라이언트 사전질문을 크롤(로그인 세션 사용).

usage: python wishket_fetch.py <project_id>
출력 JSON: {project_id, title, description, pre_questions: [...]}
env: SESSIONS_DIR  (wishket-storage.json 위치)
"""

import os
import sys
import json

from playwright.sync_api import sync_playwright

SESSIONS = os.environ.get("SESSIONS_DIR", "./sessions")
STATE = os.path.join(SESSIONS, "wishket-storage.json")
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def main(pid: str):
    out = {"project_id": pid, "title": "", "description": "", "pre_questions": []}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        ctx = br.new_context(storage_state=STATE, locale="ko-KR", user_agent=UA)
        pg = ctx.new_page()
        pg.set_default_timeout(30000)

        # 1) 공고 상세
        pg.goto(f"https://www.wishket.com/project/{pid}/", wait_until="domcontentloaded")
        pg.wait_for_timeout(2000)
        out["title"] = pg.title().split(" · ")[0].strip()
        try:
            out["description"] = pg.locator(".project-description").first.inner_text().strip()
        except Exception as e:
            out["description"] = f"(description fetch failed: {e})"

        # 2) 사전질문 — 지원 페이지의 '클라이언트의 질문' (필수 질문은 '*'로 끝남)
        pg.goto(
            f"https://www.wishket.com/project/{pid}/proposal/apply/",
            wait_until="domcontentloaded",
        )
        pg.wait_for_timeout(2000)
        if "/accounts/login" in pg.url or "auth.wishket.com" in pg.url:
            out["pre_questions"] = ["(session expired — run wishket_login.py)"]
        else:
            cand = pg.eval_on_selector_all(
                "label,h3,h4,strong,p",
                "els=>[...new Set(els.map(e=>e.innerText.trim()))]",
            )
            qs = []
            for t in cand:
                if not t or len(t) > 200:
                    continue
                # 클라이언트 질문은 보통 물음형이거나 '*'로 끝나는 필수 항목
                if (t.endswith("*") or t.endswith("?") or "주세요" in t or "있나요" in t) and (
                    "금액" not in t and "기간" not in t and "근무 시작" not in t
                    and "관련 경력" not in t and "이력서" not in t and "지원 내용" not in t
                ):
                    qs.append(t.rstrip(" *"))
            # 중복 제거 보존
            seen = set()
            out["pre_questions"] = [q for q in qs if not (q in seen or seen.add(q))]

        br.close()
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: wishket_fetch.py <project_id>")
        sys.exit(1)
    main(sys.argv[1])
