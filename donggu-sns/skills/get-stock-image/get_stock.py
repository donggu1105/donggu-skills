#!/usr/bin/env python3
"""get-stock-image — 키워드+종류로 적절한 무료 스톡 소스를 자동 라우팅해 이미지 1장 저장.

Usage:
  python3 get_stock.py "<keyword>" <out_path> [--kind photo|illustration|real|concept]
                       [--orientation portrait|landscape|square] [--index N]
                       [--source unsplash|pexels|pixabay|commons|openverse]

종류(kind)별 폴백 순서 — 앞 소스 실패/무키면 다음으로 자동 진행:
  photo        → unsplash → pexels → pixabay     (감성·브랜드 무드 사진)
  illustration → pixabay → openverse             (벡터·일러스트)
  real         → commons → openverse → pexels    (실제 사물·인물·역사)
  concept      → pixabay → unsplash → pexels      (추상 개념)
--source 로 특정 소스만 강제할 수도 있다.

키(.env): PEXELS_API_KEY, UNSPLASH_ACCESS_KEY, PIXABAY_API_KEY
무키 소스: commons(Wikimedia), openverse — 키 없이 즉시 동작.

저장 후 반드시 Read로 주제 적합성을 눈으로 확인하고, 어긋나면 --index 를 올려 재시도.
반환 JSON 의 license 필드를 발행 시 출처표기 판단에 쓴다(특히 commons·openverse).
"""
import os, sys, json, argparse, urllib.request, urllib.parse

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

_ENV_KEYS = ("PEXELS_API_KEY", "UNSPLASH_ACCESS_KEY", "PIXABAY_API_KEY")


def _load_env():
    """키를 환경에 자동 주입 — 이미 export된 값은 그대로 두고, 없으면 알려진 .env에서 읽는다.
    탐색: $GET_STOCK_ENV → ~/workspace/projects/n8n/.env → ~/.env → 이 스킬 폴더의 .env.
    덕분에 매번 export 없이 동작한다(commons·openverse는 무키라 키 없이도 됨)."""
    if all(os.environ.get(k) for k in _ENV_KEYS):
        return
    here = os.path.dirname(os.path.abspath(__file__))
    for c in (os.environ.get("GET_STOCK_ENV"),
              os.path.expanduser("~/workspace/projects/n8n/.env"),
              os.path.expanduser("~/.env"),
              os.path.join(here, ".env")):
        if not c or not os.path.isfile(c):
            continue
        try:
            for line in open(c, encoding="utf-8"):
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                if k in _ENV_KEYS and not os.environ.get(k):
                    os.environ[k] = v.strip().strip('"').strip("'")
        except Exception:
            pass
        if any(os.environ.get(k) for k in _ENV_KEYS):
            break


def _download(url, out):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r, open(out, "wb") as f:
        f.write(r.read())


def pexels(kw, out, orientation, idx):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    q = urllib.parse.urlencode({"query": kw, "orientation": orientation,
                                "per_page": 10, "size": "large"})
    req = urllib.request.Request("https://api.pexels.com/v1/search?" + q,
                                 headers={"Authorization": key, "User-Agent": UA})
    photos = json.load(urllib.request.urlopen(req, timeout=20)).get("photos", [])
    if not photos:
        return None
    p = photos[min(idx, len(photos) - 1)]
    src = p["src"].get("large2x") or p["src"]["large"]
    _download(src, out)
    return {"source": "pexels", "credit": p.get("photographer"),
            "page": p.get("url"), "license": "Pexels (free, attribution optional)"}


def unsplash(kw, out, orientation, idx):
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    if not key:
        return None
    o = {"portrait": "portrait", "landscape": "landscape",
         "square": "squarish"}.get(orientation, "landscape")
    q = urllib.parse.urlencode({"query": kw, "orientation": o, "per_page": 10})
    req = urllib.request.Request("https://api.unsplash.com/search/photos?" + q,
                                 headers={"Authorization": "Client-ID " + key,
                                          "User-Agent": UA})
    res = json.load(urllib.request.urlopen(req, timeout=20)).get("results", [])
    if not res:
        return None
    p = res[min(idx, len(res) - 1)]
    _download(p["urls"]["regular"], out)
    return {"source": "unsplash", "credit": p["user"]["name"],
            "page": p["links"]["html"], "alt": p.get("alt_description"),
            "license": "Unsplash (free, attribution appreciated)"}


def pixabay(kw, out, orientation, idx):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    q = urllib.parse.urlencode({"key": key, "q": kw, "per_page": 10,
                                "safesearch": "true", "image_type": "all"})
    req = urllib.request.Request("https://pixabay.com/api/?" + q,
                                 headers={"User-Agent": UA})
    hits = json.load(urllib.request.urlopen(req, timeout=20)).get("hits", [])
    if not hits:
        return None
    h = hits[min(idx, len(hits) - 1)]
    _download(h.get("largeImageURL") or h["webformatURL"], out)
    return {"source": "pixabay", "credit": h.get("user"),
            "page": h.get("pageURL"), "license": "Pixabay (free, attribution optional)"}


def commons(kw, out, orientation, idx):
    # Wikimedia Commons — 무키. 식별 UA 필수(위키미디어 정책).
    s = urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": "filetype:bitmap " + kw, "gsrnamespace": 6, "gsrlimit": 10,
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 1280,
    })
    req = urllib.request.Request(
        "https://commons.wikimedia.org/w/api.php?" + s,
        headers={"User-Agent": "donggu-get-stock/1.0 (https://donggu.site)"})
    pages = json.load(urllib.request.urlopen(req, timeout=20)).get(
        "query", {}).get("pages", {})
    items = [p for p in pages.values() if p.get("imageinfo")]
    if not items:
        return None
    items.sort(key=lambda p: p.get("index", 0))
    it = items[min(idx, len(items) - 1)]
    ii = it["imageinfo"][0]
    _download(ii.get("thumburl") or ii["url"], out)
    lic = ii.get("extmetadata", {}).get("LicenseShortName", {}).get("value", "CC/PD")
    return {"source": "commons", "credit": it.get("title"),
            "page": ii.get("descriptionurl"), "license": lic}


def openverse(kw, out, orientation, idx):
    # Openverse — 무키(익명 허용). 상업적 사용 가능 라이선스만.
    q = urllib.parse.urlencode({"q": kw, "page_size": 10,
                                "license_type": "commercial"})
    req = urllib.request.Request("https://api.openverse.org/v1/images/?" + q,
                                 headers={"User-Agent": UA})
    res = json.load(urllib.request.urlopen(req, timeout=25)).get("results", [])
    if not res:
        return None
    r = res[min(idx, len(res) - 1)]
    _download(r.get("url"), out)
    lic = (r.get("license", "") + " " + str(r.get("license_version", ""))).strip()
    return {"source": "openverse", "credit": r.get("creator"),
            "page": r.get("foreign_landing_url"), "license": "CC " + lic}


LADDERS = {
    "photo": ["unsplash", "pexels", "pixabay"],
    "illustration": ["pixabay", "openverse"],
    "real": ["commons", "openverse", "pexels"],
    "concept": ["pixabay", "unsplash", "pexels"],
}
FNS = {"pexels": pexels, "unsplash": unsplash, "pixabay": pixabay,
       "commons": commons, "openverse": openverse}


def main():
    _load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("keyword")
    ap.add_argument("out")
    ap.add_argument("--kind", default="photo", choices=list(LADDERS))
    ap.add_argument("--orientation", default="landscape",
                    choices=["portrait", "landscape", "square"])
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--source", choices=list(FNS))
    a = ap.parse_args()
    order = [a.source] if a.source else LADDERS[a.kind]
    tried = []
    for name in order:
        try:
            r = FNS[name](a.keyword, a.out, a.orientation, a.index)
            if r:
                r.update({"saved": a.out, "keyword": a.keyword, "kind": a.kind,
                          "fallback_order": order})
                print(json.dumps(r, ensure_ascii=False))
                return
            tried.append(f"{name}:no-result-or-no-key")
        except Exception as e:
            tried.append(f"{name}:{type(e).__name__}")
    sys.exit("all sources failed → " + "; ".join(tried))


if __name__ == "__main__":
    main()
