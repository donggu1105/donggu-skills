#!/usr/bin/env python3
"""Fetch a topic-relevant photo from Pexels into a card deck's assets/.

Usage:
  PEXELS_API_KEY=xxx python3 pexels_fetch.py "<keyword>" <out_path.jpg> [orientation] [index]

- keyword: search terms derived from the card's topic (e.g. "ui design figma")
- out_path: where to save (e.g. assets/card-2-design.jpg)
- orientation: portrait | landscape | square  (default portrait for 4:5 cards)
- index: which result to take (0-based; bump to retry a different photo if the
         first one isn't relevant after you Read it)

Always Read the saved file afterward and confirm the subject matches the card.
Pexels License: free, commercial use OK, attribution appreciated not required.
"""
import os, sys, json, urllib.request, urllib.parse

key = os.environ.get("PEXELS_API_KEY")
if not key:
    sys.exit("PEXELS_API_KEY not set")

kw = sys.argv[1]
out = sys.argv[2]
orientation = sys.argv[3] if len(sys.argv) > 3 else "portrait"
idx = int(sys.argv[4]) if len(sys.argv) > 4 else 0

q = urllib.parse.urlencode({
    "query": kw, "orientation": orientation, "per_page": 10, "size": "large",
})
# Pexels' edge blocks the default Python-urllib UA → must send a browser-like UA
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
req = urllib.request.Request("https://api.pexels.com/v1/search?" + q,
                             headers={"Authorization": key, "User-Agent": UA})
data = json.load(urllib.request.urlopen(req, timeout=20))
photos = data.get("photos", [])
if not photos:
    sys.exit(f"No Pexels results for: {kw}")
if idx >= len(photos):
    idx = 0
p = photos[idx]
# pick a large-ish portrait-friendly rendition
src = p["src"].get("portrait") or p["src"].get("large2x") or p["src"]["large"]
img_req = urllib.request.Request(src, headers={"User-Agent": UA})
with urllib.request.urlopen(img_req, timeout=30) as r, open(out, "wb") as f:
    f.write(r.read())
print(json.dumps({
    "saved": out, "keyword": kw, "index": idx, "total": len(photos),
    "photographer": p.get("photographer"), "url": p.get("url"),
    "avg_color": p.get("avg_color"),
}, ensure_ascii=False))
