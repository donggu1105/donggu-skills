"""Wishket 로그인 세션 캡처/점검 — CDP 기반 단계별 점검.

영속 프로필(`wishket-profile`)을 쓰되, CDP 디버그 포트를 열어 떠 있는 브라우저에
별도 프로세스가 붙어 상태를 점검할 수 있게 한다. 사람이 로그인하는 과정을
"하나씩" 확인하기 위함.

모드:
  launch : 영속 프로필 + CDP(기본 9222)로 headed 브라우저를 띄워 위시켓 로그인
           페이지로 이동. session-token 쿠키가 감지되면 자동 저장 후 종료(최대 30분).
  probe  : 떠 있는 브라우저에 CDP로 붙어 현재 URL/타이틀/로그인여부/스크린샷 점검.

env: SESSIONS_DIR, SCREENSHOTS_DIR, WISHKET_CDP_PORT(기본 9222)
"""

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = Path(os.environ.get("SESSIONS_DIR", "./sessions")) / "wishket-profile"
# fetch/fill이 재사용하는 storage_state 스냅샷. 로그인 성공 시 여기에 저장한다.
STATE = Path(os.environ.get("SESSIONS_DIR", "./sessions")) / "wishket-storage.json"
SHOTS = Path(os.environ.get("SCREENSHOTS_DIR", "./screenshots"))
CDP_PORT = int(os.environ.get("WISHKET_CDP_PORT", "9222"))
LOGIN_URL = "https://www.wishket.com/accounts/login/"


def _login_tokens(cookies):
    # 위시켓 로그인 표식: www.wishket.com의 Django 세션(wsessionid) + 인증토큰(WART).
    # auth.wishket.com 프론트는 NextAuth지만 실제 세션은 wsessionid/WART로 유지된다.
    auth = {"wsessionid", "WART"}
    return [c["name"] for c in cookies if c["name"] in auth or "session-token" in c["name"]]


def launch():
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            args=[f"--remote-debugging-port={CDP_PORT}"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URL)
        print(f"[launch] CDP={CDP_PORT} 로그인 진행하세요(창 닫지 마세요).", flush=True)
        deadline = time.time() + 1800
        while time.time() < deadline:
            time.sleep(2)
            try:
                if _login_tokens(ctx.cookies()):
                    print("[launch] LOGIN_DETECTED", flush=True)
                    time.sleep(2)  # 쿠키 flush 여유
                    break
                if len(ctx.pages) == 0:
                    break
            except Exception:
                break
        # fetch/fill이 쓰는 storage_state 스냅샷 저장 (브라우저 닫기 전에)
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            ctx.storage_state(path=str(STATE))
            print(f"[launch] state saved {STATE}", flush=True)
        except Exception as e:
            print(f"[launch] state save failed: {e}", flush=True)
        try:
            ctx.close()
        except Exception:
            pass
        print(f"[launch] saved {PROFILE}", flush=True)


def probe():
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        ctx = b.contexts[0]
        cookies = ctx.cookies()
        tok = _login_tokens(cookies)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        shot = SHOTS / "wishket_probe.png"
        try:
            page.screenshot(path=str(shot))
        except Exception as e:
            print("SHOT_FAIL:", e)
            shot = None
        print("URL:", page.url)
        try:
            print("TITLE:", page.title())
        except Exception:
            pass
        print("LOGGED_IN" if tok else "NOT_LOGGED_IN", tok)
        wk = [(c["name"], c["domain"]) for c in cookies if "wishket" in c["domain"]]
        print("WISHKET_COOKIES:", wk)
        if shot:
            print("SHOT:", shot)
        b.close()  # CDP 연결만 끊김 — 브라우저는 유지


def _read_creds():
    """자격증명을 env 또는 파일에서 읽는다. 파일 우선(ps/env 노출 회피).

    파일 형식(.env 스타일): WISHKET_ID=..., WISHKET_PW=...
    """
    wid = os.environ.get("WISHKET_ID")
    wpw = os.environ.get("WISHKET_PASSWORD") or os.environ.get("WISHKET_PW")
    cf = os.environ.get("WISHKET_CRED_FILE")
    if cf and os.path.exists(cf):
        for line in open(cf, encoding="utf-8"):
            line = line.strip()
            if line.startswith("WISHKET_ID="):
                wid = line.split("=", 1)[1].strip()
            elif line.startswith("WISHKET_PASSWORD=") or line.startswith("WISHKET_PW="):
                wpw = line.split("=", 1)[1].strip()
    return wid, wpw


def autologin():
    """떠 있는 브라우저(CDP)에 자격증명을 입력하고 로그인 버튼 클릭 → 결과 점검."""
    wid, wpw = _read_creds()
    if not wid or not wpw:
        print("NO_CREDS — set WISHKET_CRED_FILE or WISHKET_ID/WISHKET_PW")
        return
    SHOTS.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        ctx = b.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        if "auth.wishket.com" not in page.url:
            page.goto(LOGIN_URL)
            page.wait_for_timeout(1500)
        page.fill("input[name=emailOrId]", wid)
        page.fill("input[name=password]", wpw)
        try:
            page.check("input[name=remember]")
        except Exception:
            pass
        page.get_by_role("button", name="로그인", exact=True).click()
        ok = False
        for _ in range(25):
            page.wait_for_timeout(1000)
            if _login_tokens(ctx.cookies()):
                ok = True
                break
        page.wait_for_timeout(1000)
        try:
            page.screenshot(path=str(SHOTS / "wishket_after_login.png"))
        except Exception:
            pass
        if ok:
            try:
                STATE.parent.mkdir(parents=True, exist_ok=True)
                ctx.storage_state(path=str(STATE))
                print("STATE_SAVED", STATE)
            except Exception as e:
                print("STATE_SAVE_FAILED", e)
        print("URL", page.url)
        print("LOGGED_IN" if ok else "NOT_LOGGED_IN", _login_tokens(ctx.cookies()))
        # 화면상 에러 메시지 있으면 노출
        try:
            body = page.inner_text("body")
            for kw in ("일치하지", "올바르지", "확인", "오류", "로봇", "captcha", "보안"):
                for ln in body.splitlines():
                    if kw in ln and len(ln) < 80:
                        print("MSG:", ln.strip())
                        break
        except Exception:
            pass
        b.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "probe"
    fn = {"launch": launch, "probe": probe, "autologin": autologin}.get(mode)
    if not fn:
        print("usage: python scripts/wishket_login.py <launch|probe|autologin>")
        sys.exit(1)
    fn()
