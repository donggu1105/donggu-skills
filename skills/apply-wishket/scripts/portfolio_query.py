"""portfolio Supabase에서 관련 프로젝트를 조회 — 제안서 생성의 단일 소스(SSOT).

`projects` 테이블(slug, title, summary, role, problem, solution, impact_summary,
tags TEXT[], features — 본문은 *_i18n JSONB ko/en)에서 공고 스택과 겹치는
프로젝트를 점수순으로 반환한다.

env:
  PORTFOLIO_SUPABASE_URL   예: https://ggvlnurppgoroqxbhpej.supabase.co
  PORTFOLIO_SUPABASE_KEY   anon 또는 service key (projects read 권한)
usage:
  python portfolio_query.py --tags "Next.js,Supabase,React" --limit 6 [--locale ko]
출력: JSON {"projects": [...]}
"""

import os
import sys
import json
import argparse
import urllib.request

BASE = os.environ.get("PORTFOLIO_SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("PORTFOLIO_SUPABASE_KEY", "")


def _get(path: str):
    url = f"{BASE}/rest/v1/{path}"
    req = urllib.request.Request(
        url, headers={"apikey": KEY, "Authorization": f"Bearer {KEY}"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _pick(row: dict, locale: str = "ko") -> dict:
    def L(field):
        v = row.get(f"{field}_i18n")
        if isinstance(v, dict):
            return v.get(locale) or v.get("ko") or v.get("en")
        return row.get(field)

    return {
        "slug": row.get("slug"),
        "title": L("title"),
        "summary": L("summary"),
        "role": L("role"),
        "problem": L("problem"),
        "solution": L("solution"),
        "impact_summary": L("impact_summary"),
        "features": L("features") or row.get("features") or [],
        "tags": row.get("tags") or [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="", help="comma-separated stack keywords")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--locale", default="ko")
    a = ap.parse_args()
    if not BASE or not KEY:
        print(json.dumps({"error": "PORTFOLIO_SUPABASE_URL/KEY not set"}))
        sys.exit(1)

    rows = _get("projects?select=*")
    items = [_pick(r, a.locale) for r in rows]

    wanted = [t.strip().lower() for t in a.tags.split(",") if t.strip()]
    if wanted:
        def score(it):
            tg = [str(x).lower() for x in (it.get("tags") or [])]
            blob = " ".join([str(it.get(k) or "") for k in ("title", "summary", "solution")]).lower()
            return sum(1 for w in wanted if any(w in t for t in tg) or w in blob)

        ranked = sorted(items, key=score, reverse=True)
        matched = [it for it in ranked if score(it) > 0]
        items = matched or ranked

    print(json.dumps({"projects": items[: a.limit]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
