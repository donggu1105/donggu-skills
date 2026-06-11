#!/usr/bin/env python3
"""Fetch a REAL image of a named subject from Wikimedia Commons.

Use for specific, named real things — a real place (한강 / Han River), product,
person, brand, landmark, logo — where a generic stock photo would be wrong.
Commons images are freely licensed (CC / public domain); attribution varies by
file, so the helper prints the descriptionurl for the user to check.

Usage:
  python3 commons_fetch.py "<query>" <out.jpg> [width] [index]

  query: the real subject, e.g. "Han River Seoul night", "n8n logo"
  out:   save path (e.g. assets/hero-hangang.jpg)
  width: target px width (default 1280)
  index: which search hit (0-based; bump to retry a different file)

Always Read the saved file and confirm it's the right subject before using —
Commons search can return maps, diagrams, or unrelated files.
"""
import os, sys, json, urllib.request, urllib.parse

UA = "donggu-cardnews/1.0 (https://github.com/donggu1105/donggu-skills; contact via github)"
query = sys.argv[1]
out = sys.argv[2]
width = int(sys.argv[3]) if len(sys.argv) > 3 else 1280
idx = int(sys.argv[4]) if len(sys.argv) > 4 else 0

params = {
    "action": "query", "format": "json",
    "generator": "search", "gsrsearch": query, "gsrnamespace": "6",  # File:
    "gsrlimit": "10", "prop": "imageinfo",
    "iiprop": "url|extmetadata|mime", "iiurlwidth": str(width),
}
url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
req = urllib.request.Request(url, headers={"User-Agent": UA})
data = json.load(urllib.request.urlopen(req, timeout=20))
pages = list((data.get("query", {}).get("pages", {}) or {}).values())
# keep only raster images (skip svg/pdf/tif), sorted by search index
imgs = []
for p in pages:
    ii = (p.get("imageinfo") or [{}])[0]
    mime = ii.get("mime", "")
    if mime in ("image/jpeg", "image/png", "image/webp") and ii.get("thumburl"):
        imgs.append((p.get("index", 999), p.get("title"), ii))
imgs.sort(key=lambda x: x[0])
if not imgs:
    sys.exit(f"No usable Commons image for: {query}")
if idx >= len(imgs):
    idx = 0
_, title, ii = imgs[idx]
src = ii["thumburl"]
meta = ii.get("extmetadata", {})
img_req = urllib.request.Request(src, headers={"User-Agent": UA})
with urllib.request.urlopen(img_req, timeout=30) as r, open(out, "wb") as f:
    f.write(r.read())
print(json.dumps({
    "saved": out, "query": query, "index": idx, "total": len(imgs),
    "title": title, "descriptionurl": ii.get("descriptionurl"),
    "license": (meta.get("LicenseShortName", {}) or {}).get("value"),
    "artist": (meta.get("Artist", {}) or {}).get("value", "")[:120],
}, ensure_ascii=False))
