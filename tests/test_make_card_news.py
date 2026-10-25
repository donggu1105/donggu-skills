"""Contracts for donggu-docs:make-card-news.

Pure checks always run. The render check needs a headless Chrome/Chromium and is
skipped when none is installed (the renderer itself reports that case clearly).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "donggu-docs"
SKILL = PACKAGE / "skills" / "make-card-news"
RENDERER = SKILL / "scripts" / "render_cards.py"
sys.path.insert(0, str(SKILL / "scripts"))

import render_cards  # noqa: E402  (imported after sys.path tweak)


def manifest_scalar(path: Path, key: str) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    raise AssertionError(f"{key} missing in {path}")


class PackagingTest(unittest.TestCase):
    def test_skill_files_and_runtime_neutral_wording(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: make-card-news\n"))
        for banned in ("AskUserQuestion", "skill_view(", "MEDIA:", "~/.hermes/profiles"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, text)
        for required in (
            SKILL / "scripts" / "render_cards.py",
            SKILL / "templates" / "card.html",
            SKILL / "themes" / "beyond-deploy.json",
            SKILL / "themes" / "donggu.json",
            SKILL / "references" / "card-spec.md",
            SKILL / "references" / "platform-specs.md",
            SKILL / "references" / "tool-landscape.md",
            SKILL / "examples" / "sample-bd.json",
        ):
            with self.subTest(path=required.relative_to(ROOT)):
                self.assertTrue(required.is_file())

    def test_docs_plugin_version_bumped_everywhere(self):
        claude = json.loads((PACKAGE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entry = next(item for item in marketplace["plugins"] if item["name"] == "donggu-docs")
        self.assertEqual(claude["version"], entry["version"])
        self.assertEqual("1.2.0", claude["version"])
        readme = (PACKAGE / "README.md").read_text(encoding="utf-8")
        self.assertIn("skills-2", readme)
        self.assertIn("make-card-news", readme)
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("donggu-docs:make-card-news", root_readme)
        self.assertIn("v1.2.0", root_readme)

    def test_sns_package_still_free_of_card_news(self):
        # The SNS domain retired its card-news skill on purpose; the new skill lives in docs.
        for path in (PACKAGE.parent / "donggu-sns").rglob("*.md"):
            self.assertNotIn("make-card-news", path.read_text(encoding="utf-8"), path)


class SpecAndHtmlTest(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads((SKILL / "examples" / "sample-bd.json").read_text(encoding="utf-8"))
        # classic-layout contracts are checked against a classic copy; the sample itself ships cinematic
        self.spec = {k: v for k, v in self.sample.items() if k != "layout"}
        self.theme = render_cards.load_theme("beyond-deploy", SKILL)

    def test_sample_spec_validates_and_covers_every_card_type(self):
        cards = render_cards.validate_spec(self.spec)
        self.assertGreaterEqual(len(cards), 5)
        self.assertEqual({c["type"] for c in cards}, set(render_cards.CARD_TYPES))

    def test_validate_rejects_unknown_type_and_missing_fields(self):
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"cards": [{"type": "hero", "title": "x"}]})
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"cards": [{"type": "point", "title": "제목만"}]})
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"cards": []})
        with self.assertRaises(render_cards.SpecError):  # stat needs value + label
            render_cards.validate_spec({"cards": [{"type": "stat", "value": "100"}]})
        with self.assertRaises(render_cards.SpecError):  # one number per slide: value must be short
            render_cards.validate_spec({"cards": [{"type": "stat", "value": "1,234,567,890", "label": "x"}]})

    def test_closing_cta_is_a_platform_native_action_not_a_fake_button(self):
        # Nothing inside a card image is clickable (Instagram: no links at all; LinkedIn strips links
        # from document PDFs). A URL or a "click/tap" verb in the cta is a fake affordance → reject.
        base = {"type": "closing", "title": "t"}
        for bad in ("https://beyonddeploy.kr", "beyonddeploy.kr/newsletter 클릭", "여기를 눌러 신청", "링크를 탭하세요"):
            with self.assertRaises(render_cards.SpecError, msg=bad):
                render_cards.validate_spec({"cards": [dict(base, cta=bad)]})
        ok = render_cards.validate_spec({"cards": [dict(base, cta="신청 링크는 프로필과 댓글에")]})
        self.assertEqual(ok[0]["cta"], "신청 링크는 프로필과 댓글에")
        html = render_cards.build_card_html(dict(base, cta="저장해 두고 다음 모임 전에 다시 보기"),
                                            index=1, total=1, spec=self.spec, theme=self.theme)
        self.assertIn('data-qa="cta"', html)
        self.assertNotRegex(html, r"\.cta\s*\{[^}]*border-radius:\s*999px")  # not drawn as a button
        # the sample set must follow the rule too
        closing = [c for c in self.sample["cards"] if c["type"] == "closing"]
        self.assertTrue(closing)
        for c in closing:
            self.assertNotRegex(c.get("cta", ""), r"https?://|\.kr|\.com|클릭|눌러|탭")

    def test_stat_card_markup_puts_number_first_and_names_the_source(self):
        card = {"type": "stat", "kicker": "케이스 토크 4회차 동안", "value": "100", "unit": "여 명",
                "label": "FDE와 AX 실무자를 만났습니다", "context": "첫 모임은 두 FDE의 사례로 시작했습니다.",
                "source": "beyonddeploy.kr 필드노트"}
        html = render_cards.build_card_html(card, index=3, total=8, spec=self.spec, theme=self.theme)
        self.assertIn('class="stat"', html)
        self.assertLess(html.index('data-qa="value"'), html.index('data-qa="label"'))
        self.assertIn('data-qa="source"', html)
        self.assertIn("type-stat", html)
        # label is headline-sized: it shares the .title size token, not the body one
        self.assertRegex(html, r"\.stat-label\s*\{[^}]*font-size:\s*var\(--title-size\)")

    def test_html_escapes_and_keeps_korean_word_breaks(self):
        card = {"type": "point", "title": "<script>x</script>", "body": "줄1\n**강조**"}
        html = render_cards.build_card_html(card, index=1, total=3, spec=self.spec, theme=self.theme)
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("<br>", html)
        self.assertIn("<strong", html)
        self.assertIn("word-break: keep-all", html)
        self.assertIn("1080px", html)
        self.assertIn("1350px", html)
        self.assertIn("01 / 03", html)
        self.assertIn(self.theme["accent"], html)
        self.assertIn('data-qa-result', html)  # QA probe script is embedded

    def test_sample_ships_its_photos(self):
        cards = render_cards.validate_spec(self.sample)
        self.assertTrue(all(c.get("image") for c in cards), "every sample card carries a photo")
        spec_dir = SKILL / "examples"
        for c in cards:
            if c.get("image"):
                p = render_cards.resolve_image(c["image"]["src"], spec_dir)
                self.assertTrue(p.is_file(), p)
                self.assertLess(p.stat().st_size, 400_000, f"{p.name}: keep sample photos small")
                self.assertTrue(c["image"].get("alt"), f"{c['type']}: image needs alt text")

    def test_image_spec_validation(self):
        base = {"type": "point", "title": "t", "body": "b"}
        for bad in (
            {"src": "x.gif"},                        # unsupported extension
            {"src": "x.jpg", "mode": "hero"},        # unknown mode
            {"src": "x.jpg", "zoom": 3},             # zoom out of range
            {"src": "x.jpg", "fade": 1.5},           # fade out of range
            "assets/x.jpg",                          # must be an object
        ):
            with self.assertRaises(render_cards.SpecError, msg=bad):
                render_cards.validate_spec({"cards": [dict(base, image=bad)]})
        with self.assertRaises(render_cards.SpecError):  # compare takes no inline image
            render_cards.validate_spec({"cards": [{"type": "compare", "title": "t",
                "left": {"title": "a", "body": "b"}, "right": {"title": "c", "body": "d"},
                "image": {"src": "x.jpg", "mode": "inline"}}]})
        with self.assertRaises(render_cards.SpecError):  # URLs are not fetched
            render_cards.resolve_image("https://example.com/a.jpg", SKILL)
        with self.assertRaises(render_cards.SpecError):  # missing file
            render_cards.resolve_image("assets/does-not-exist.jpg", SKILL / "examples")

    def test_image_modes_render_to_distinct_markup(self):
        img = SKILL / "examples" / "assets" / "lounge-wide.jpg"
        for mode, needle in (("full", 'class="bg"'), ("band", 'class="band"'), ("inline", 'class="inline-img"')):
            card = {"type": "point", "title": "t", "body": "b",
                    "image": {"src": str(img), "mode": mode, "focus": "30% 40%", "overlay": 0.8, "zoom": 1.2}}
            html = render_cards.build_card_html(card, index=1, total=1, spec=self.spec, theme=self.theme,
                                                spec_dir=SKILL / "examples")
            self.assertIn(needle, html, mode)
            self.assertIn(f"mode-{mode}", html)
            self.assertIn("--focus: 30% 40%", html)
            self.assertIn("--zoom: 1.2", html)
            self.assertIn(img.as_uri(), html)  # file:// so Chrome can load it without a server
            self.assertIn('data-qa-img', html)  # probe reports load state
        plain = render_cards.build_card_html({"type": "point", "title": "t", "body": "b"},
                                             index=1, total=1, spec=self.spec, theme=self.theme)
        self.assertIn("mode-text", plain)
        self.assertNotIn("<img", plain)  # no spec_dir → no wash either; relative src must never leak into HTML
        no_bd = dict(self.spec); no_bd.pop("backdrop", None)
        plain2 = render_cards.build_card_html({"type": "point", "title": "t", "body": "b"},
                                              index=1, total=1, spec=no_bd, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertNotIn("<img", plain2)

    def test_backdrop_wash_ties_text_and_band_cards_to_the_cover(self):
        img = SKILL / "examples" / "assets" / "lounge-wide.jpg"
        spec = dict(self.spec, backdrop={"src": str(img), "tint": 0.84})
        # text card: set-level backdrop becomes a blurred wash behind the content
        text = render_cards.build_card_html({"type": "point", "title": "t", "body": "b"},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertIn('class="wash"', text)
        self.assertIn('data-qa-img="wash"', text)
        self.assertRegex(text, r'<div class="card [^"]*has-wash')
        self.assertIn("--wash-tint: 0.84", text)
        # band card: wash comes from its own photo so the band dissolves into itself
        other = SKILL / "examples" / "assets" / "lounge-close.jpg"
        band = render_cards.build_card_html({"type": "point", "title": "t", "body": "b",
                                             "image": {"src": str(other), "mode": "band"}},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertIn('class="band"', band)
        self.assertEqual(band.count(other.as_uri()), 2, "band photo should appear as band and as wash")
        self.assertNotIn(img.as_uri(), band)
        # full-bleed card: no wash (the cover look is untouched)
        full = render_cards.build_card_html({"type": "cover", "title": "t",
                                             "image": {"src": str(other), "mode": "full"}},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertNotIn('class="wash"', full)
        self.assertNotRegex(full, r'<div class="card [^"]*has-wash')
        # per-card opt-out
        bare = render_cards.build_card_html({"type": "point", "title": "t", "body": "b", "wash": False},
                                            index=1, total=1, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
        self.assertNotIn('class="wash"', bare)
        # sample ships with a backdrop (cinematic: photo fallback; classic: wash)
        self.assertIn("backdrop", self.sample)
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"backdrop": {"src": "x.gif"}, "cards": [{"type": "point", "title": "t", "body": "b"}]})


class CinematicLayoutTest(unittest.TestCase):
    """`layout: "cinematic"` — the cover treatment on every card: photo + dark gradient + white type,
    no rules, no pills, no page counter. Chosen by the user over the chrome-heavy default."""

    def setUp(self):
        self.spec = json.loads((SKILL / "examples" / "sample-bd.json").read_text(encoding="utf-8"))
        self.theme = render_cards.load_theme("beyond-deploy", SKILL)
        self.img = SKILL / "examples" / "assets" / "lounge-wide.jpg"

    def _html(self, card, spec=None):
        spec = dict(spec or self.spec, layout="cinematic")
        return render_cards.build_card_html(card, index=2, total=8, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")

    def test_sample_ships_cinematic_and_every_card_has_a_photo(self):
        self.assertEqual(self.spec.get("layout"), "cinematic")
        for c in render_cards.validate_spec(self.spec):
            self.assertTrue(c.get("image") or self.spec.get("backdrop"), f"{c['type']}: cinematic cards need a photo (own image or set backdrop)")

    def test_cinematic_has_no_chrome(self):
        html = self._html({"type": "point", "title": "t", "body": "b", "image": {"src": str(self.img)}})
        body = html[html.index("<body>"):]
        self.assertNotIn('class="meta"', body)          # no series pill
        self.assertNotIn("02 / 08", body)               # no page counter
        self.assertNotIn('class="footer"', body)        # no footer rule
        self.assertIn('class="bg"', body)               # photo fills the card
        self.assertIn("layout-cinematic", body)
        self.assertNotRegex(html, r"\.layout-cinematic[^{]*\{[^}]*border-top")
        self.assertNotIn("beyonddeploy.kr", body)        # middle cards carry no handle either

    def test_cinematic_handle_only_on_first_and_last_card_without_page_counter(self):
        spec = dict(self.spec, layout="cinematic")
        for idx in (1, 8):
            html = render_cards.build_card_html({"type": "point", "title": "t", "body": "b", "image": {"src": str(self.img)}},
                                                index=idx, total=8, spec=spec, theme=self.theme, spec_dir=SKILL / "examples")
            body = html[html.index("<body>"):]
            self.assertIn("beyonddeploy.kr", body)
            self.assertNotIn(f"{idx:02d} / 08", body)

    def test_cinematic_falls_back_to_backdrop_when_card_has_no_image(self):
        spec = dict(self.spec, backdrop={"src": str(self.img)})
        html = self._html({"type": "point", "title": "t", "body": "b"}, spec)
        self.assertIn('class="bg"', html)
        self.assertIn(self.img.as_uri(), html)
        with self.assertRaises(render_cards.SpecError):   # no photo anywhere → refuse, don't render a black card
            render_cards.validate_spec({"layout": "cinematic", "cards": [{"type": "point", "title": "t", "body": "b"}]})

    def test_cinematic_accent_comes_from_the_theme(self):
        donggu = render_cards.load_theme("donggu", SKILL)
        html = render_cards.build_card_html({"type": "point", "title": "t", "body": "b", "image": {"src": str(self.img)}},
                                            index=2, total=8, spec=dict(self.spec, layout="cinematic"), theme=donggu,
                                            spec_dir=SKILL / "examples")
        self.assertIn(f"--accent-on-dark: {donggu['accent_on_dark']}", html)
        self.assertNotIn("#cfe8a9", html)   # BD green must not leak into other themes
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"layout": "cinematic", "backdrop": {"src": "a.jpg", "overlay": 3},
                                        "cards": [{"type": "point", "title": "t", "body": "b"}]})

    def test_unknown_layout_rejected_and_default_still_classic(self):
        with self.assertRaises(render_cards.SpecError):
            render_cards.validate_spec({"layout": "neon", "cards": [{"type": "point", "title": "t", "body": "b"}]})
        spec = {k: v for k, v in self.spec.items() if k != "layout"}
        html = render_cards.build_card_html({"type": "point", "title": "t", "body": "b"}, index=1, total=1, spec=spec, theme=self.theme)
        self.assertIn('class="meta"', html)
        self.assertIn("01 / 01", html)


class VaultHandoffTest(unittest.TestCase):
    """`vault_handoff.py` files a rendered set into the Obsidian vault the way the vault's own rules want it:
    assets first (copied + hashed), then one channel note that links them, then an INDEX line. Nothing is
    published and nothing outside the target folders is touched."""

    def _fake_render(self, tmp: Path) -> tuple[Path, Path]:
        spec_src = SKILL / "examples" / "sample-bd.json"
        spec = json.loads(spec_src.read_text(encoding="utf-8"))
        spec_dir = tmp / "spec"; (spec_dir / "assets").mkdir(parents=True)
        for img in (SKILL / "examples" / "assets").glob("*.jpg"):
            shutil.copy(img, spec_dir / "assets" / img.name)
        (spec_dir / "cards.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
        out = tmp / "out"; out.mkdir()
        for i in range(1, len(spec["cards"]) + 1):
            (out / f"{i:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([i]) * 64)
        (out / "cards.pdf").write_bytes(b"%PDF-1.4 fake")
        (out / "qa.json").write_text(json.dumps({"problems": [], "cards_total": len(spec["cards"]),
                                                 "cards": [{"font_available": True}] * len(spec["cards"])}), encoding="utf-8")
        return spec_dir / "cards.json", out

    def _fake_vault(self, tmp: Path) -> Path:
        vault = tmp / "vault"
        area = vault / "FDE 커뮤니티 (Beyond Deploy)"
        (area / "Content" / "Instagram").mkdir(parents=True)
        (area / "Content" / "CardNews").mkdir()
        (area / "Content" / "INDEX - Content.md").write_text("---\ntype: index\nupdated: 2026-10-21\n---\n\n# Beyond Deploy 콘텐츠\n\n## 연결\n\n[[x]]\n", encoding="utf-8")
        (area / "Content" / "CardNews" / "INDEX - CardNews.md").write_text(
            "---\ntype: index\nupdated: 2026-10-25\n---\n\n# 카드뉴스\n\n## 세트\n\n- a\n\n## 원고 탐색\n\n```base\nx\n```\n", encoding="utf-8")
        (area / "Content" / "Instagram" / "INDEX - Instagram.md").write_text(
            "---\ntype: index\nupdated: 2026-09-08\n---\n\n# 인스타그램\n\n## 케이스 토크 01\n\n- a\n\n## 원고 탐색\n\n```base\nx\n```\n", encoding="utf-8")
        return vault

    def test_handoff_files_assets_note_and_index_lines(self):
        self.assertTrue((SKILL / "scripts" / "vault_handoff.py").is_file(), "scripts/vault_handoff.py missing")
        import vault_handoff as vh  # scripts dir is on sys.path (see top of file)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            spec_path, out = self._fake_render(tmp)
            vault = self._fake_vault(tmp)
            res = vh.handoff(spec_path=spec_path, out_dir=out, vault=vault, area="FDE 커뮤니티 (Beyond Deploy)",
                             channels=["instagram", "linkedin"], title="4번의 모임, 100여 명의 FDE를 만나며 알게 된 것들",
                             date="2026-10-25", source_url="https://beyonddeploy.kr/field-notes/four-rounds-hundred-fdes",
                             caption="캡션 초안", consent_note="정장·조끼 두 분 동의 미확인",
                             extra_sources=[], dry_run=False)
            area = vault / "FDE 커뮤니티 (Beyond Deploy)"
            # one folder per set: note + PNGs + PDF + editable spec + assets + manifest, all side by side
            folder = area / "Content" / "CardNews" / "2026-10-25 - 4번의 모임, 100여 명의 FDE를 만나며 알게 된 것들"
            self.assertTrue(folder.is_dir(), res)
            for f in ("01.png", "08.png", "cards.pdf", "cards.json", "MANIFEST.md",
                      "CardNews - 4번의 모임, 100여 명의 FDE를 만나며 알게 된 것들.md"):
                self.assertTrue((folder / f).is_file(), f)
            self.assertTrue((folder / "assets" / "lounge-wide.jpg").is_file())
            self.assertFalse((area / "Attachments").exists())           # nothing scattered into Attachments
            self.assertFalse(list((area / "Content" / "Instagram").glob("Instagram - 4번의 모임*")))
            manifest = (folder / "MANIFEST.md").read_text(encoding="utf-8")
            self.assertIn(hashlib.sha256((folder / "01.png").read_bytes()).hexdigest(), manifest)
            self.assertNotIn("supabase.co", manifest)                  # no signed URLs leak into the vault
            body = (folder / "CardNews - 4번의 모임, 100여 명의 FDE를 만나며 알게 된 것들.md").read_text(encoding="utf-8")
            fm = body.split("---")[1]
            self.assertIn("type: channel_pack", fm); self.assertIn("format: card-news", fm)
            self.assertIn("channels: [instagram, linkedin]", fm)
            self.assertIn("status: draft", fm); self.assertIn("area: fde-community", fm)
            self.assertNotIn("published_at:", fm)                     # draft: no publish fields invented
            self.assertIn("FDE는 어디까지", body)                        # per-card copy is in the note
            self.assertIn("![[01.png]]", body)                        # same-folder embeds, no long paths
            self.assertIn("[[MANIFEST]]", body)
            self.assertIn("make-card-news", body)                     # points at the skill, doesn't restate its rules
            self.assertIn("동의 미확인", body)
            for idx in ("Content/INDEX - Content.md", "Content/CardNews/INDEX - CardNews.md"):
                txt = (area / idx).read_text(encoding="utf-8")
                self.assertIn("4번의 모임", txt, idx)
                self.assertIn("updated: 2026-10-25", txt, idx)
            self.assertNotIn("4번의 모임", (area / "Content" / "Instagram" / "INDEX - Instagram.md").read_text(encoding="utf-8"))
            # idempotent: second run with the same inputs changes nothing and refuses to overwrite the note silently
            res2 = vh.handoff(spec_path=spec_path, out_dir=out, vault=vault, area="FDE 커뮤니티 (Beyond Deploy)",
                              channels=["instagram"], title="4번의 모임, 100여 명의 FDE를 만나며 알게 된 것들",
                              date="2026-10-25", source_url="https://beyonddeploy.kr/x", caption="캡션 초안",
                              consent_note="x", extra_sources=[], dry_run=False)
            self.assertEqual(res2["note"]["status"], "exists")
            self.assertEqual((area / "Content" / "INDEX - Content.md").read_text(encoding="utf-8").count("CardNews - 4번의 모임"), 1)

    def test_handoff_refuses_a_set_that_failed_qa_or_lacks_pngs(self):
        import vault_handoff as vh
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            spec_path, out = self._fake_render(tmp)
            vault = self._fake_vault(tmp)
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8")); qa["problems"] = [{"card": 2, "kind": "overflow"}]
            (out / "qa.json").write_text(json.dumps(qa), encoding="utf-8")
            with self.assertRaises(vh.HandoffError):
                vh.handoff(spec_path=spec_path, out_dir=out, vault=vault, area="FDE 커뮤니티 (Beyond Deploy)", channels=["instagram"],
                           title="t", date="2026-10-25", source_url="", caption="", consent_note="", extra_sources=[], dry_run=True)
            self.assertFalse(any((vault / "FDE 커뮤니티 (Beyond Deploy)" / "Content" / "CardNews").glob("2026-*")))


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.chrome = render_cards.find_chrome(os.environ.get("CARD_NEWS_CHROME"))
        if not self.chrome:
            self.skipTest("no headless Chrome/Chromium available")

    def test_renders_png_set_pdf_and_qa_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            proc = subprocess.run(
                [sys.executable, str(RENDERER), str(SKILL / "examples" / "sample-bd.json"),
                 "--out", str(out), "--theme", "beyond-deploy"],
                capture_output=True, text=True, timeout=240,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            pngs = sorted(out.glob("[0-9][0-9].png"))
            spec = json.loads((SKILL / "examples" / "sample-bd.json").read_text(encoding="utf-8"))
            self.assertEqual(len(pngs), len(spec["cards"]))
            self.assertTrue((out / "cards.pdf").is_file())
            self.assertEqual(len(sorted((out / "html").glob("*.html"))), len(pngs))
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertEqual(qa["cards_total"], len(pngs))
            self.assertEqual(qa["problems"], [], qa)
            self.assertTrue(qa["cards"][0]["font_available"], qa["cards"][0])
            try:
                from PIL import Image
            except ImportError:  # pragma: no cover
                return
            with Image.open(pngs[0]) as im:
                self.assertEqual(im.size, (1080, 1350))

    def test_overflowing_body_is_reported_and_exit_code_2(self):
        spec = {
            "theme": "beyond-deploy",
            "handle": "@test",
            "cards": [
                {"type": "point", "title": "넘침 테스트", "body": "가나다라 마바사 " * 120},
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "out"
            proc = subprocess.run(
                [sys.executable, str(RENDERER), str(spec_path), "--out", str(out), "--no-pdf"],
                capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertTrue(any(p["kind"] == "overflow" for p in qa["problems"]), qa)

    def test_classic_layout_still_renders_clean_without_the_lines(self):
        # the older white/wash/band look stays supported; its top bar and footer rule are gone (user: "줄있는거부터가 별로")
        template = (SKILL / "templates" / "card.html").read_text(encoding="utf-8")
        self.assertNotRegex(template, r"\.card::before\s*\{[^}]*background")
        self.assertNotRegex(template, r"\.footer\s*\{[^}]*border-top")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            proc = subprocess.run([sys.executable, str(RENDERER), str(SKILL / "examples" / "sample-bd-classic.json"),
                                   "--out", str(out), "--no-pdf"], capture_output=True, text=True, timeout=240)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertEqual(json.loads((out / "qa.json").read_text(encoding="utf-8"))["problems"], [])

    def test_broken_image_is_reported_not_silently_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.jpg"
            bad.write_bytes(b"not really a jpeg")
            spec = {"theme": "beyond-deploy", "handle": "@test", "cards": [
                {"type": "point", "title": "이미지 깨짐", "body": "본문", "image": {"src": "bad.jpg", "mode": "band"}}]}
            spec_path = Path(tmp) / "spec.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")
            out = Path(tmp) / "out"
            proc = subprocess.run([sys.executable, str(RENDERER), str(spec_path), "--out", str(out), "--no-pdf"],
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            qa = json.loads((out / "qa.json").read_text(encoding="utf-8"))
            self.assertTrue(any(p["kind"] == "image" for p in qa["problems"]), qa)


if __name__ == "__main__":
    unittest.main()
