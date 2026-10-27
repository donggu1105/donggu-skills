#!/usr/bin/env python3
"""
prepare_story.py — make-story-image 출력 폴더(`NN.jpg` + `qa.json`)와 인스타그램 채널 노트에서
스토리 발행 payload(`image_url` + `account`)를 프레임마다 하나씩 준비한다.

흐름: qa.json 확인(problems 비어 있음, frames_total = 디스크의 NN.jpg 수) → 매직바이트(JPEG) →
노트 frontmatter `account:` 해석(prepare_instagram.resolve_account 그대로) → Supabase storage(public 버킷)에
upsert 업로드 → 어댑터 프리뷰(operation=story)에 그대로 넣을 JSON 배열을 stdout으로.

스토리는 피드 글 위에 얹는 2차 게시라 `status: published` 노트도 막지 않는다. 노트에 `## 스토리`
섹션이 없으면 경고(no_story_section)만 남긴다. Graph API 스토리는 이미지 1장·JPEG·캡션 없음·
스티커 불가 — 링크 스티커가 필요하면 앱에서 올린다(make-story-image 참고).

사용:
  python3 prepare_story.py "<Instagram - 제목.md>" --frames <OUT_DIR> [--frame N] \
      [--account donggu|beyonddeploy] [--slug SLUG] [--bucket sns-media] [--dry-run]
계정: prepare_instagram.py와 같은 규칙(frontmatter가 정본, --account는 교차 확인, `beyond-deploy` 별칭).
키(.env 자동탐색, prepare_blog_images.load_env): SUPABASE_SERVICE_KEY, SUPABASE_URL
  탐색: $SNS_ENV → ~/workspace/projects/n8n/.env → ~/.env   (--dry-run이면 읽지 않음)
storage 경로: instagram/<YYYY>/<MM-DD>/<slug>-story-<HHMMSS>/<NN>.jpg  (NN = 프레임 번호)
topic: "<노트 제목> (스토리 N)" — 같은 노트의 피드 글과 장부 행이 갈린다.
종료코드: 0=성공, 1=업로드 실패, 2=규격 위반(QA 문제·프레임 수 불일치·account 없음/허용값 밖 등),
         3=NN.jpg가 실제 JPEG 바이트가 아님
출력(stdout): payload JSON 배열. (stderr): 로그 JSON 한 줄씩. 비밀값은 어디에도 넣지 않는다.
"""
import argparse
import datetime
import json
import os
import re
import sys
import urllib.error
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
import prepare_blog_images as blog  # noqa: E402  .env·로그·업로드 규칙을 공유한다
import prepare_instagram as ig  # noqa: E402  frontmatter·account·slug·storage 규칙을 공유한다

PrepareError = ig.PrepareError

CHANNEL = ig.CHANNEL
OPERATION = "story"
STORY_SECTION = "스토리"
FRAME_RE = re.compile(r"^(\d{2})\.jpg$")
JPEG_MAGIC = b"\xff\xd8\xff"


def read_qa(frames_dir: Path):
    """qa.json → (frames_total, problems). 없거나 깨졌으면 PrepareError(2)."""
    qa_path = frames_dir / "qa.json"
    if not qa_path.is_file():
        raise PrepareError(2, f"qa.json 없음: {qa_path} — make-story-image 출력 폴더인지 확인")
    try:
        qa = json.loads(qa_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError):
        raise PrepareError(2, "qa.json을 JSON으로 읽지 못함") from None
    total = qa.get("frames_total") if isinstance(qa, dict) else None
    if isinstance(total, bool) or not isinstance(total, int) or total < 1:
        raise PrepareError(2, "qa.json frames_total이 1 이상의 정수가 아님")
    problems = qa.get("problems")
    if not isinstance(problems, list):
        raise PrepareError(2, "qa.json problems가 목록이 아님")
    return total, problems


def list_frames(frames_dir: Path, total):
    """디스크의 `NN.jpg`(01부터 빈 번호 없이). 수·번호가 qa.json과 다르면 PrepareError(2)."""
    names = sorted(p.name for p in frames_dir.iterdir() if p.is_file() and FRAME_RE.match(p.name))
    if len(names) != total:
        raise PrepareError(
            2, f"qa.json frames_total {total}장인데 NN.jpg {len(names)}장 — 다시 렌더",
            files=names,
        )
    expected = [f"{i:02d}.jpg" for i in range(1, total + 1)]
    if names != expected:
        raise PrepareError(2, "NN.jpg 번호가 01부터 이어지지 않음", files=names)
    return [frames_dir / name for name in names]


def check_jpeg(paths):
    """확장자는 .jpg인데 바이트가 JPEG이 아니면 PrepareError(3)."""
    bad = []
    for path in paths:
        with open(path, "rb") as fh:
            head = fh.read(16)
        if not head.startswith(JPEG_MAGIC):
            bad.append(path.name)
            blog.log({
                "extension_mismatch": path.name,
                "real_format": blog.sniff_format(head) or "unrecognized",
                "magic": head[:8].hex(),
                "fix": blog.mismatch_fix(path.name, blog.sniff_format(head), ".jpg"),
            })
    if bad:
        raise PrepareError(3, f"{len(bad)}개 프레임이 JPEG 바이트가 아님 — 업로드 중단", files=bad)


def prepare(a, warnings):
    note_path = Path(a.note).resolve()
    if not note_path.is_file():
        raise PrepareError(2, f"노트 없음: {note_path}")
    frames_dir = Path(a.frames).resolve()
    if not frames_dir.is_dir():
        raise PrepareError(2, f"프레임 폴더 없음: {frames_dir}")

    total, problems = read_qa(frames_dir)
    if problems:
        raise PrepareError(2, f"qa.json problems {len(problems)}건 — 고친 뒤 다시 렌더",
                           problems=problems[:20])
    paths = list_frames(frames_dir, total)
    check_jpeg(paths)

    fm, body = ig._split_frontmatter(note_path.read_text(encoding="utf-8").replace("\r\n", "\n"))
    channel = fm.get("channel", "")
    if channel != CHANNEL:
        raise PrepareError(2, f"channel이 instagram이 아님: {channel or '(없음)'}")
    account = ig.resolve_account(fm, a.account, warnings)
    if STORY_SECTION not in ig._sections(body):
        ig._warn(warnings, "no_story_section")

    if a.frame is not None:
        if not 1 <= a.frame <= total:
            raise PrepareError(2, f"--frame {a.frame} — 1~{total} 사이여야 함")
        selected = [(a.frame, paths[a.frame - 1])]
    else:
        selected = list(enumerate(paths, 1))

    slug = a.slug or ig.default_slug(note_path)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", slug):
        raise PrepareError(2, f"slug는 ASCII 영숫자·'-'만 허용(storage InvalidKey 방지): {slug!r}")
    folder = ig.storage_folder(f"{slug}-story", datetime.datetime.now())

    urls = {}
    if a.dry_run:
        urls = {n: f"dry-run://{n:02d}" for n, _ in selected}
    else:
        blog.load_env()
        base_url = (os.environ.get("SUPABASE_URL") or blog.DEFAULT_URL).rstrip("/")
        service_key = os.environ.get("SUPABASE_SERVICE_KEY")
        if not service_key:
            raise PrepareError(2, "SUPABASE_SERVICE_KEY 없음 — .env 확인")
        for n, path in selected:
            key_path = ig.object_key(folder, n, path)
            try:
                url = blog.upload(str(path), key_path, a.bucket, base_url, service_key)
            except urllib.error.HTTPError as exc:
                body = exc.read()[:300].decode("utf-8", "replace")
                raise PrepareError(1, f"업로드 실패 {path.name}: HTTP {exc.code}",
                                   response=body, uploaded=len(urls))
            except (urllib.error.URLError, OSError) as exc:
                raise PrepareError(1, f"업로드 실패 {path.name}: {exc}", uploaded=len(urls))
            urls[n] = url
            blog.log({"uploaded": path.name, "url": url})

    title = ig.note_topic(note_path, fm)
    payloads = [
        {
            "channel": CHANNEL,
            "operation": OPERATION,
            "topic": f"{title} (스토리 {n})",
            "note_path": str(note_path),
            "payload": {"image_url": urls[n], "account": account},
        }
        for n, _ in selected
    ]
    return payloads, folder


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("note")
    ap.add_argument("--frames", required=True, help="make-story-image 출력 폴더(NN.jpg + qa.json)")
    ap.add_argument("--frame", type=int, default=None, help="이 프레임 하나만(1부터)")
    ap.add_argument("--account", default=None,
                    help=f"발행 계정({'|'.join(ig.ACCOUNTS)}) — frontmatter account와 다르면 종료코드 2")
    ap.add_argument("--slug", default=None, help="storage 경로 슬러그(생략 시 노트 파일명에서)")
    ap.add_argument("--bucket", default="sns-media")
    ap.add_argument("--dry-run", action="store_true", help="업로드 없이 payload 모양만 출력")
    a = ap.parse_args(argv)

    warnings = []
    try:
        payloads, folder = prepare(a, warnings)
    except PrepareError as exc:
        blog.log({"error": exc.message, "exit_code": exc.code, **exc.details})
        return exc.code

    sys.stdout.write(json.dumps(payloads, ensure_ascii=False, indent=2) + "\n")
    blog.log({"done": True, "count": len(payloads), "folder": folder,
              "dry_run": bool(a.dry_run), "warnings": len(warnings)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
