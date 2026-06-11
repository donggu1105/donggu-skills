#!/usr/bin/env python3
"""Upload a card-news image set to Supabase Storage with a dated, ordered path.

Path convention (browsable + cleanup-friendly + collision-safe):
  <channel>/<YYYY>/<MM-DD>/<topic-slug>-<HHMMSS>/<NN><ext>
  e.g. instagram/2026/06-12/yeopjari-launch-142305/01.png

One carousel set = one folder. Card order is preserved by zero-padded index.
Returns the public URLs in order (carousel order) as JSON.

Env:
  SUPABASE_URL          e.g. https://fvfayignxybdyyravorg.supabase.co
  SUPABASE_SERVICE_KEY  service_role key (server-side upload, bypasses RLS)

Usage:
  python3 supabase_upload.py <channel> <topic-slug> <bucket> file1.png file2.png ...
  # files are uploaded in the order given → that IS the carousel order
"""
import os, sys, json, datetime, urllib.request, mimetypes

url = os.environ.get("SUPABASE_URL", "").rstrip("/")
key = os.environ.get("SUPABASE_SERVICE_KEY")
if not url or not key:
    sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

channel, slug, bucket = sys.argv[1], sys.argv[2], sys.argv[3]
files = sys.argv[4:]
if not files:
    sys.exit("no files given")

now = datetime.datetime.now()
folder = f"{channel}/{now:%Y}/{now:%m-%d}/{slug}-{now:%H%M%S}"

public = []
for i, path in enumerate(files, 1):
    ext = os.path.splitext(path)[1] or ".png"
    key_path = f"{folder}/{i:02d}{ext}"
    ctype = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as f:
        body = f.read()
    req = urllib.request.Request(
        f"{url}/storage/v1/object/{bucket}/{key_path}",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": ctype,
                 "x-upsert": "true"},
    )
    urllib.request.urlopen(req, timeout=30)
    public.append(f"{url}/storage/v1/object/public/{bucket}/{key_path}")

print(json.dumps({"folder": folder, "count": len(public), "image_urls": public},
                 ensure_ascii=False))
