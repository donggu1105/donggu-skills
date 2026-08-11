#!/usr/bin/env python3
"""Upload finalized local image files to Supabase Storage in stable order.

Path convention:
  <channel>/<YYYY>/<MM-DD>/<topic-slug>-<HHMMSS>/<NN><ext>

Usage:
  python3 upload_images.py <channel> <topic-slug> <bucket> file1.png file2.png ...

The input order is preserved in the returned ``image_urls`` JSON array.
"""
import os, sys, json, datetime, urllib.request, mimetypes

url = os.environ.get("SUPABASE_URL", "").rstrip("/")
key = os.environ.get("SUPABASE_SERVICE_KEY")
if not url or not key:
    sys.exit("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

channel, slug, bucket = sys.argv[1], sys.argv[2], sys.argv[3]
files = sys.argv[4:]
if not 1 <= len(files) <= 10:
    sys.exit("upload_images.py requires 1–10 image files")

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
