#!/usr/bin/env python3
"""prepare_instagram.py — 노트 파싱·게이트·업로드 경로 계약.

네트워크·실제 vault 없이 돈다: 노트는 fixture 문자열, vault는 tempfile 폴더(.obsidian 포함),
업로드는 urllib.request.urlopen mock.
"""
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import runpy
import struct
import sys
import tempfile
import unittest
import urllib.error
import zlib
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "publish-sns"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SKILL_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MOD = _load("prepare_instagram")

SET_DIR = "Attachments/2026-10-25 - 테스트 모임 회고 (카드뉴스)"
KAKAO_LINK = "Content/KakaoTalk/KakaoTalk - 현장 사진 사용 고지"
NOTE_NAME = "Instagram - 4번의 모임, 100여 명을 만나며 알게 된 것들.md"
CAPTION = (
    "4번의 모임에서 100여 명의 실무자를 만났습니다.\n"
    "\n"
    "주제도 업종도 달랐는데 꺼내 놓는 고민은 비슷했습니다. 결국 서로의 사례가 기준이 됐습니다.\n"
    "\n"
    "#BeyondDeploy #비욘드디플로이 #FDE #AX #케이스토크 #AI전환 #오프라인밋업 #커뮤니티"
)
MEMO = "링크드인(회사 페이지)에는 `cards.pdf`를 문서로 올리고, 본문은 회사 페이지 화자로 다시 쓴다."
CARD_TYPES = ["cover", "quote", "stat", "list", "point", "compare", "steps", "closing"]


def png_bytes(seed):
    """1×1 PNG(매직바이트 포함). seed마다 픽셀이 달라 SHA-256도 다르다."""
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    raw = b"\x00" + bytes([seed % 256, 0, 0])
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b""))


def jpeg_bytes(seed):
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + bytes([seed % 256]) * 8 + b"\xff\xd9"


def note_text(*, channel="instagram", status="draft", files=None, caption_block=None,
              consent=True, cards=None, account="beyonddeploy"):
    files = [f"{i:02d}.png" for i in range(1, 9)] if files is None else files
    cards_section = "".join(
        f"### {i:02d} · {CARD_TYPES[(i - 1) % len(CARD_TYPES)]}\n"
        f"![[{SET_DIR}/{name}]]\n- 제목: 카드 {i}\n\n"
        for i, name in enumerate(files, 1)
    )
    caption_block = f"{CAPTION}\n\n{MEMO}" if caption_block is None else caption_block
    consent_section = (
        "## 사진과 동의\n\n현장 사진 4장.\n\n"
        "### 공개 사용 검토\n\n"
        "- 판정: **고지 후 게시 가능** — 게시 전 오픈카톡방 고지로 빈틈을 메운다.\n"
        f"- 고지문: [[{KAKAO_LINK}|KakaoTalk - 현장 사진 사용 고지]] (초안)\n"
        f"- 사진 원본·해시: [[{SET_DIR}/MANIFEST|MANIFEST]]\n\n"
        if consent else ""
    )
    return (
        "---\n"
        "type: channel_pack\n"
        f"channel: {channel}\n"
        + (f"account: {account}\n" if account is not None else "")
        + f"status: {status}\n"
        f"cards: {len(files) if cards is None else cards}\n"
        "topics: [beyond-deploy, case-talk]\n"
        "sources:\n"
        '  - "[[Content/GUIDE - 콘텐츠 방향과 기준]]"\n'
        "---\n\n"
        "# 4번의 모임, 100여 명을 만나며 알게 된 것들\n\n"
        "> [!note] 카드 8장 · 미게시\n\n"
        "## 장별 카피\n\n"
        f"{cards_section}"
        "## 캡션 초안 (인스타그램)\n\n"
        f"{caption_block}\n\n"
        f"{consent_section}"
        "## 편집 판단\n\n- 디자인 메모.\n"
    )


class FixedDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 26, 9, 8, 7)


class VaultCase(unittest.TestCase):
    """임시 vault: .obsidian + 이미지 8장 + MANIFEST + 카톡 고지 노트."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name).resolve()
        (self.vault / ".obsidian").mkdir()
        self.set_dir = self.vault / SET_DIR
        self.set_dir.mkdir(parents=True)
        for i in range(1, 9):
            (self.set_dir / f"{i:02d}.png").write_bytes(png_bytes(i))
        self.write_manifest()
        self.write_kakao("draft")
        self.note = self.vault / "Content" / "Instagram" / NOTE_NAME
        self.note.parent.mkdir(parents=True)
        self.write_note(note_text())

    def tearDown(self):
        self._tmp.cleanup()

    def write_note(self, text):
        self.note.write_text(text, encoding="utf-8")

    def write_kakao(self, status):
        path = self.vault / f"{KAKAO_LINK}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"---\ntype: channel_pack\nchannel: kakaotalk\nstatus: {status}\n---\n\n# 고지\n",
                        encoding="utf-8")

    def write_manifest(self):
        rows = "".join(
            f"| {p.name} | {hashlib.sha256(p.read_bytes()).hexdigest()} | {p.stat().st_size} |\n"
            for p in sorted(self.set_dir.iterdir()) if p.name != "MANIFEST.md"
        )
        (self.set_dir / "MANIFEST.md").write_text(
            f"# MANIFEST\n\n| 파일 | SHA-256 | 바이트 |\n|---|---|---|\n{rows}", encoding="utf-8"
        )

    def run_main(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = MOD.main([str(self.note), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def dry_run_ok(self, *args):
        code, out, err = self.run_main("--dry-run", *args)
        self.assertEqual(0, code, err)
        return json.loads(out)


class ParseNoteTests(unittest.TestCase):
    def test_bd_shaped_note_keeps_embed_order_and_trims_caption_at_hashtag_line(self):
        note = MOD.parse_instagram_note(note_text())
        self.assertEqual("instagram", note.frontmatter["channel"])
        self.assertEqual("8", note.frontmatter["cards"])
        self.assertEqual([f"{SET_DIR}/{i:02d}.png" for i in range(1, 9)], note.embeds)
        self.assertEqual(CAPTION, note.caption)
        self.assertNotIn("링크드인", note.caption)
        self.assertTrue(note.caption.endswith("#커뮤니티"))
        self.assertEqual([KAKAO_LINK], note.consent_links)
        self.assertTrue(note.consent_required)
        self.assertEqual([], note.warnings)

    def test_note_order_is_canonical_and_filename_order_mismatch_warns(self):
        files = ["01.png", "03.png", "02.png"]
        note = MOD.parse_instagram_note(note_text(files=files))
        self.assertEqual([f"{SET_DIR}/{n}" for n in files], note.embeds)
        mismatched = [w for w in note.warnings if w["code"] == "embed_order_mismatch"]
        self.assertEqual([2, 3], [w["position"] for w in mismatched])

    def test_caption_without_hashtag_line_uses_whole_section_and_warns(self):
        note = MOD.parse_instagram_note(note_text(caption_block="첫 단락.\n\n둘째 단락."))
        self.assertEqual("첫 단락.\n\n둘째 단락.", note.caption)
        self.assertIn("no_hashtag_line", [w["code"] for w in note.warnings])

    def test_plain_caption_heading_is_accepted(self):
        text = note_text().replace("## 캡션 초안 (인스타그램)", "## 캡션")
        self.assertEqual(CAPTION, MOD.parse_instagram_note(text).caption)

    def test_no_consent_section_means_no_consent_gate(self):
        note = MOD.parse_instagram_note(note_text(consent=False))
        self.assertFalse(note.consent_required)
        self.assertEqual([], note.consent_links)

    def test_cards_frontmatter_mismatch_warns(self):
        note = MOD.parse_instagram_note(note_text(cards=9))
        self.assertIn("cards_count_mismatch", [w["code"] for w in note.warnings])

    def test_default_slug_is_ascii_only_with_dated_fallback(self):
        # Supabase Storage는 비ASCII 키를 InvalidKey(400)로 거부한다(2026-10-26 실측).
        fixed = datetime.datetime(2026, 10, 26, 10, 0, 0)
        self.assertEqual("ig-20261026", MOD.default_slug(NOTE_NAME, now=fixed))
        self.assertEqual("ig-20261026", MOD.default_slug("Instagram - " + "가" * 80 + ".md", now=fixed))
        self.assertEqual(
            "four-rounds-100-fdes", MOD.default_slug("Instagram - Four Rounds, 100 FDEs!.md")
        )
        self.assertTrue(MOD.default_slug("Instagram - " + "a" * 80 + ".md").isascii())
        self.assertLessEqual(len(MOD.default_slug("Instagram - " + "a" * 80 + ".md")), 60)


class ResolveEmbedTests(unittest.TestCase):
    def test_vault_relative_path_resolves_exactly_and_never_escapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp).resolve()
            (vault / "a").mkdir()
            (vault / "b").mkdir()
            (vault / "a" / "01.png").write_bytes(png_bytes(1))
            (vault / "b" / "01.png").write_bytes(png_bytes(2))
            self.assertEqual(vault / "b" / "01.png", MOD.resolve_embed(vault, "b/01.png"))
            with self.assertRaises(FileNotFoundError):
                MOD.resolve_embed(vault, "c/01.png")  # 다른 폴더의 01.png를 집지 않는다
            outside = vault.parent / "outside.png"
            with self.assertRaises(FileNotFoundError):
                MOD.resolve_embed(vault, f"a/../../{outside.name}")
            self.assertEqual(vault / "a" / "01.png", MOD.resolve_embed(vault, "01.png"))


class GateTests(VaultCase):
    def test_bd_shaped_note_dry_run_succeeds(self):
        self.write_kakao("published")
        result = self.dry_run_ok()
        self.assertEqual(8, result["image_count"])
        self.assertEqual(CAPTION, result["payload"]["caption"])
        self.assertEqual(8, result["hashtags"])
        self.assertEqual(len(CAPTION), result["caption_chars"])
        self.assertEqual(str(self.note), result["note_path"])
        self.assertEqual("4번의 모임, 100여 명을 만나며 알게 된 것들", result["topic"])
        self.assertEqual("publish", result["operation"])
        self.assertIn("png_will_be_reencoded_by_instagram", [w["code"] for w in result["warnings"]])

    def test_frontmatter_account_reaches_payload_and_top_level(self):
        self.write_kakao("published")
        result = self.dry_run_ok()
        self.assertEqual("beyonddeploy", result["account"])
        self.assertEqual("beyonddeploy", result["payload"]["account"])
        self.assertEqual({"image_urls", "caption", "account"}, set(result["payload"]))
        keys = list(result)
        self.assertEqual(keys.index("caption_first_line") - 1, keys.index("account"))
        self.write_note(note_text(account="donggu"))
        self.assertEqual("donggu", self.dry_run_ok()["payload"]["account"])

    def test_missing_or_unknown_account_exits_2(self):
        # 폴더(Content/Instagram)나 vault 위치로 계정을 추정하지 않는다.
        self.write_kakao("published")
        for account in (None, "", "x", "Donggu"):
            with self.subTest(account=account):
                self.write_note(note_text(account=account))
                code, out, err = self.run_main("--dry-run")
                self.assertEqual(2, code)
                self.assertEqual("", out)
                self.assertIn("account", err)

    def test_cli_account_must_match_frontmatter(self):
        self.write_kakao("published")
        code, out, err = self.run_main("--dry-run", "--account", "donggu")
        self.assertEqual(2, code)
        self.assertEqual("", out)
        self.assertIn("beyonddeploy", err)
        self.assertEqual(2, self.run_main("--dry-run", "--account", "x")[0])
        self.assertEqual("beyonddeploy", self.dry_run_ok("--account", "beyonddeploy")["account"])

    def test_cli_account_alone_is_explicit_but_warns(self):
        self.write_kakao("published")
        self.write_note(note_text(account=None))
        result = self.dry_run_ok("--account", "donggu")
        self.assertEqual("donggu", result["payload"]["account"])
        self.assertIn("account_from_cli_only", [w["code"] for w in result["warnings"]])

    def test_non_instagram_channel_exits_2(self):
        self.write_note(note_text(channel="threads"))
        self.assertEqual(2, self.run_main("--dry-run")[0])

    def test_caption_length_limit(self):
        self.write_kakao("published")
        tail = "\n\n#ab"
        self.write_note(note_text(caption_block="가" * (2201 - len(tail)) + tail))
        self.assertEqual(2, self.run_main("--dry-run")[0])
        self.write_note(note_text(caption_block="가" * (2200 - len(tail)) + tail))
        self.assertEqual(2200, self.dry_run_ok()["caption_chars"])

    def test_hashtag_count_limit(self):
        self.write_kakao("published")
        self.write_note(note_text(caption_block="본문\n\n" + " ".join(f"#t{i}" for i in range(31))))
        self.assertEqual(2, self.run_main("--dry-run")[0])
        self.write_note(note_text(caption_block="본문\n\n" + " ".join(f"#t{i}" for i in range(30))))
        self.assertEqual(30, self.dry_run_ok()["hashtags"])

    def test_empty_caption_and_leftover_embed_exit_2(self):
        self.write_note(note_text(caption_block=""))
        self.assertEqual(2, self.run_main("--dry-run")[0])
        self.write_note(note_text(caption_block="본문 ![[x.png]]\n\n#태그"))
        self.assertEqual(2, self.run_main("--dry-run")[0])

    def test_embed_count_must_be_1_to_10(self):
        for count in (0, 11):
            with self.subTest(count=count):
                self.write_note(note_text(files=[f"{i:02d}.png" for i in range(1, count + 1)]))
                self.assertEqual(2, self.run_main("--dry-run")[0])

    def test_png_bytes_named_jpg_exits_3_with_sips_fix(self):
        self.write_kakao("published")
        (self.set_dir / "05.jpg").write_bytes(png_bytes(5))
        files = [f"{i:02d}.png" for i in range(1, 9)]
        files[4] = "05.jpg"
        self.write_note(note_text(files=files))
        code, out, err = self.run_main("--dry-run")
        self.assertEqual(3, code)
        self.assertEqual("", out)
        self.assertIn("sips -s format jpeg -s formatOptions 92 '05.jpg' --out '05.jpg'", err)

    def test_non_jpeg_png_and_oversize_and_missing_files_exit_2(self):
        self.write_kakao("published")
        (self.set_dir / "01.png").unlink()
        self.assertEqual(2, self.run_main("--dry-run")[0])  # 파일 없음
        (self.set_dir / "01.gif").write_bytes(b"GIF89a" + b"\x00" * 10)
        self.write_note(note_text(files=["01.gif"]))
        self.assertEqual(2, self.run_main("--dry-run")[0])  # GIF 거부
        (self.set_dir / "big.png").write_bytes(png_bytes(9) + b"\x00" * (8 * 1024 * 1024))
        self.write_note(note_text(files=["big.png"]))
        self.assertEqual(2, self.run_main("--dry-run")[0])  # 8 MB 초과

    def test_jpeg_is_accepted_without_png_warning(self):
        self.write_kakao("published")
        (self.set_dir / "01.jpg").write_bytes(jpeg_bytes(1))
        self.write_manifest()
        self.write_note(note_text(files=["01.jpg"]))
        result = self.dry_run_ok()
        self.assertNotIn("png_will_be_reencoded_by_instagram",
                         [w["code"] for w in result["warnings"]])

    def test_manifest_hash_mismatch_exits_2_and_missing_manifest_only_warns(self):
        self.write_kakao("published")
        (self.set_dir / "03.png").write_bytes(png_bytes(99))  # 적재 뒤 파일이 바뀜
        code, _, err = self.run_main("--dry-run")
        self.assertEqual(2, code)
        self.assertIn("MANIFEST", err)
        (self.set_dir / "MANIFEST.md").unlink()
        result = self.dry_run_ok()
        self.assertIn("no_manifest", [w["code"] for w in result["warnings"]])

    def test_consent_notice_gate(self):
        code, out, err = self.run_main("--dry-run")
        self.assertEqual(4, code)
        self.assertEqual("", out)
        self.assertIn("KakaoTalk - 현장 사진 사용 고지", err)
        result = self.dry_run_ok("--force-consent")
        self.assertIn("forced_consent", [w["code"] for w in result["warnings"]])
        self.write_kakao("published")
        self.dry_run_ok()

    def test_consent_phrase_without_resolvable_notice_exits_4(self):
        (self.vault / f"{KAKAO_LINK}.md").unlink()
        self.assertEqual(4, self.run_main("--dry-run")[0])

    def test_published_note_exits_5_unless_forced(self):
        self.write_kakao("published")
        self.write_note(note_text(status="published"))
        self.assertEqual(5, self.run_main("--dry-run")[0])
        result = self.dry_run_ok("--force-republish")
        self.assertIn("forced_republish", [w["code"] for w in result["warnings"]])


class UploadTests(VaultCase):
    ENV = {"SUPABASE_URL": "https://example.supabase.co",
           "SUPABASE_SERVICE_KEY": "sk-test-secret-value-123"}

    def setUp(self):
        super().setUp()
        self.write_kakao("published")

    def upload_run(self, *args, side_effect=None):
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request)
            if side_effect:
                raise side_effect
            return mock.MagicMock()

        with mock.patch.dict(os.environ, self.ENV), mock.patch(
            "urllib.request.urlopen", side_effect=fake_urlopen
        ), mock.patch("datetime.datetime", FixedDateTime):
            code, out, err = self.run_main(*args)
        return code, out, err, calls

    def test_dry_run_fills_placeholder_urls_without_upload_or_env(self):
        out_file = self.vault / "payload.json"
        with mock.patch("urllib.request.urlopen") as urlopen, mock.patch.object(
            MOD.blog, "load_env"
        ) as load_env:
            code, out, err = self.run_main("--dry-run", "--out", str(out_file))
        self.assertEqual(0, code, err)
        result = json.loads(out)
        self.assertEqual([f"dry-run://{i:02d}" for i in range(1, 9)],
                         result["payload"]["image_urls"])
        self.assertTrue(result["dry_run"])
        urlopen.assert_not_called()
        load_env.assert_not_called()
        self.assertEqual(result, json.loads(out_file.read_text(encoding="utf-8")))

    def test_upload_path_follows_upload_images_convention_in_note_order(self):
        code, out, err, calls = self.upload_run("--slug", "bd-four-rounds")
        self.assertEqual(0, code, err)
        prefix = "https://example.supabase.co/storage/v1/object/sns-media/"
        keys = [request.full_url[len(prefix):] for request in calls]
        pattern = re.compile(r"^instagram/\d{4}/\d{2}-\d{2}/bd-four-rounds-\d{6}/(\d{2})\.png$")
        for key in keys:
            self.assertRegex(key, pattern)
        self.assertEqual([f"{i:02d}" for i in range(1, 9)], [pattern.match(k).group(1) for k in keys])
        self.assertEqual("instagram/2026/10-26/bd-four-rounds-090807/01.png", keys[0])
        self.assertEqual([png_bytes(i) for i in range(1, 9)], [request.data for request in calls])
        result = json.loads(out)
        self.assertEqual("instagram/2026/10-26/bd-four-rounds-090807", result["folder"])
        self.assertEqual(
            "https://example.supabase.co/storage/v1/object/public/sns-media/"
            "instagram/2026/10-26/bd-four-rounds-090807/01.png",
            result["payload"]["image_urls"][0],
        )
        self.assertEqual(8, result["image_count"])
        self.assertFalse(result["dry_run"])

    def test_folder_and_key_match_upload_images_script(self):
        uploader = SKILL_DIR / "upload_images.py"
        seen = []

        def fake_urlopen(request, timeout):
            seen.append(request.full_url)
            return object()

        image = self.set_dir / "01.png"
        argv = [str(uploader), "instagram", "bd", "sns-media", str(image)]
        with mock.patch.dict(os.environ, self.ENV), mock.patch("sys.argv", argv), mock.patch(
            "datetime.datetime", FixedDateTime
        ), mock.patch("urllib.request.urlopen", side_effect=fake_urlopen), \
                contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(uploader), run_name="__main__")
        folder = MOD.storage_folder("bd", FixedDateTime.now())
        self.assertEqual(
            f"https://example.supabase.co/storage/v1/object/sns-media/{MOD.object_key(folder, 1, image)}",
            seen[0],
        )

    def test_outputs_never_contain_secret_or_key_names(self):
        code, out, err, calls = self.upload_run()
        self.assertEqual(0, code, err)
        for stream in (out, err):
            self.assertNotIn("SUPABASE", stream)
            self.assertNotIn(self.ENV["SUPABASE_SERVICE_KEY"], stream)
        self.assertEqual(f"Bearer {self.ENV['SUPABASE_SERVICE_KEY']}",
                         calls[0].get_header("Authorization"))

    def test_upload_http_error_exits_1_without_payload(self):
        error = urllib.error.HTTPError("https://example.supabase.co", 400, "Bad Request", {},
                                       io.BytesIO(b'{"error":"InvalidKey"}'))
        code, out, err, calls = self.upload_run(side_effect=error)
        self.assertEqual(1, code)
        self.assertEqual("", out)
        self.assertIn("InvalidKey", err)
        self.assertNotIn(self.ENV["SUPABASE_SERVICE_KEY"], err)

    def test_non_ascii_explicit_slug_is_rejected_before_upload(self):
        code, out, err, calls = self.upload_run("--slug", "한글-슬러그")
        self.assertEqual(2, code)
        self.assertIn("InvalidKey", err)
        self.assertEqual([], calls)

    def test_hangul_note_name_gets_dated_ascii_folder(self):
        result = self.dry_run_ok()
        self.assertRegex(result["folder"], r"^instagram/\d{4}/\d{2}-\d{2}/ig-\d{8}-\d{6}$")


if __name__ == "__main__":
    unittest.main()
