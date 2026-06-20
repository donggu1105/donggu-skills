#!/usr/bin/env python3
"""
prepare_blog_images.py — tistory/maily 발행 전, 본문의 Obsidian 이미지 임베드를
공개 URL 표준 마크다운으로 바꾼다.

  ![[geudwi-hero.jpg]]  →  ![](https://….supabase.co/storage/v1/object/public/sns-media/blog/…/geudwi-hero.jpg)

흐름: 본문에서 `![[...]]` 이미지 임베드 추출 → vault에서 파일 찾기 →
Supabase storage(public 버킷)에 업로드(upsert) → 본문 치환 → 치환본을 stdout으로.

왜 필요? writing-social-content는 이미지를 vault 로컬 위키링크로 박지만,
sns-pub-tistory는 본문을 그대로 보내므로 로컬 임베드는 발행본에서 깨진다.
이 단계가 그 다리를 놓는다.

사용:
  python3 prepare_blog_images.py <note.md> [--slug SLUG] [--bucket sns-media] \
      [--out <file>]   # 생략 시 stdout
키(.env 자동탐색): SUPABASE_SERVICE_KEY, SUPABASE_URL
  탐색: $SNS_ENV → ~/workspace/projects/n8n/.env → ~/.env
종료코드: 0=치환 완료(또는 임베드 없음), 2=해결 못한 이미지 있음(업로드 안 함, 그대로 둠)
출력(stderr): 업로드/치환 로그 JSON 한 줄씩.
"""
import argparse
import datetime
import json
import mimetypes
import os
import re
import sys
import urllib.request

EMBED_RE = re.compile(r"!\[\[([^\]|]+?\.(?:jpg|jpeg|png|webp|gif))(?:\|[^\]]*)?\]\]", re.IGNORECASE)
DEFAULT_URL = "https://fvfayignxybdyyravorg.supabase.co"


def log(obj):
    sys.stderr.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_env():
    need = ("SUPABASE_SERVICE_KEY", "SUPABASE_URL")
    if all(os.environ.get(k) for k in need):
        return
    for c in (os.environ.get("SNS_ENV"),
              os.path.expanduser("~/workspace/projects/n8n/.env"),
              os.path.expanduser("~/.env")):
        if not c or not os.path.isfile(c):
            continue
        for line in open(c, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            if k in need and not os.environ.get(k):
                os.environ[k] = v.strip().strip('"').strip("'")


def find_file(basename, search_roots):
    """basename(파일명)을 search_roots 아래에서 재귀 탐색. 첫 일치 반환."""
    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if basename in files:
                return os.path.join(dirpath, basename)
    return None


def upload(local_path, key_path, bucket, base_url, service_key):
    """Supabase storage에 upsert 업로드. 성공 시 public URL 반환."""
    ctype = mimetypes.guess_type(local_path)[0] or "application/octet-stream"
    obj_url = f"{base_url}/storage/v1/object/{bucket}/{key_path}"
    with open(local_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(obj_url, data=data, method="POST", headers={
        "Authorization": f"Bearer {service_key}",
        "apikey": service_key,
        "Content-Type": ctype,
        "x-upsert": "true",
        "Cache-Control": "max-age=31536000",
    })
    urllib.request.urlopen(req, timeout=60).read()
    return f"{base_url}/storage/v1/object/public/{bucket}/{key_path}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note")
    ap.add_argument("--slug", default=None, help="storage 경로 슬러그(생략 시 이미지 폴더명 추론)")
    ap.add_argument("--bucket", default="sns-media")
    ap.add_argument("--out", default=None, help="치환본 저장 경로(생략 시 stdout)")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD storage 날짜(생략 시 오늘)")
    a = ap.parse_args()

    load_env()
    base_url = (os.environ.get("SUPABASE_URL") or DEFAULT_URL).rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not service_key:
        log({"error": "SUPABASE_SERVICE_KEY 없음 — .env 확인"})
        sys.exit(2)

    note = os.path.abspath(a.note)
    content = open(note, encoding="utf-8").read()
    note_dir = os.path.dirname(note)
    vault_root = None
    p = note_dir
    while p != os.path.dirname(p):  # vault 루트: .obsidian 보유 폴더
        if os.path.isdir(os.path.join(p, ".obsidian")):
            vault_root = p
            break
        p = os.path.dirname(p)
    search_roots = [note_dir, vault_root]

    embeds = list(dict.fromkeys(EMBED_RE.findall(content)))  # 순서보존 중복제거
    if not embeds:
        log({"info": "이미지 임베드 없음 — 본문 그대로"})
        out = content
        if a.out:
            open(a.out, "w", encoding="utf-8").write(out)
        else:
            sys.stdout.write(out)
        return

    date = a.date or datetime.date.today().isoformat()
    yyyy, mmdd = date[:4], date[5:].replace("-", "-")
    resolved, missing = {}, []
    slug = a.slug
    for name in embeds:
        fp = find_file(os.path.basename(name), search_roots)
        if not fp:
            missing.append(name)
            continue
        resolved[name] = fp
        if not slug:  # _img/<slug>/file.jpg → <slug>
            parent = os.path.basename(os.path.dirname(fp))
            slug = parent if parent and parent != "_img" else "post"

    if missing:
        for m in missing:
            log({"unresolved": m})
        log({"error": f"{len(missing)}개 이미지 못 찾음 — 업로드/치환 중단", "note": note})
        sys.exit(2)

    out = content
    for name, fp in resolved.items():
        base = os.path.basename(fp)
        key_path = f"blog/{yyyy}/{mmdd}/{slug}/{base}"
        url = upload(fp, key_path, a.bucket, base_url, service_key)
        # ![[name]] 및 ![[name|alt]] 모두 치환
        pat = re.compile(r"!\[\[" + re.escape(name) + r"(?:\|[^\]]*)?\]\]")
        out = pat.sub(f"![]({url})", out)
        log({"uploaded": base, "url": url})

    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        log({"done": True, "out": a.out, "count": len(resolved)})
    else:
        sys.stdout.write(out)
        log({"done": True, "count": len(resolved)})


if __name__ == "__main__":
    main()
