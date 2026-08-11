#!/usr/bin/env python3
import hashlib
import importlib.util
import importlib
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def manifest_scalar(path: Path, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}:\s*[\"']?([^\n\"']+)", path.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise AssertionError(f"{key} missing from {path}")
    return match.group(1).strip()


def load_package(package_dir: Path, module_name: str):
    init = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        module_name,
        init,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {init}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class FakeContext:
    def __init__(self):
        self.tools = []
        self.hooks = []
        self.skills = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))

    def register_skill(self, name, path, description=""):
        self.skills.append((name, path, description))


class NativePluginPackageTests(unittest.TestCase):
    def registered_obsidian_fixture(self, module_name):
        package = load_package(ROOT / "donggu-obsidian", module_name)
        tools = importlib.import_module(module_name + ".tools")
        runtime_module = importlib.import_module(module_name + ".runtime")
        helper = ROOT / "donggu-obsidian" / "skills" / "core-review-approval" / "scripts" / "apply-action.py"
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        vault = base / "vault"
        for name in ("10_Sources", "20_Core", "40_Channel_Packs", "50_MOCs"):
            (vault / name).mkdir(parents=True)
        source_rel = "10_Sources/source.md"
        source_bytes = b"---\ntype: source\nextracted_to: []\n---\n\n[[Broken]]\n"
        (vault / source_rel).write_bytes(source_bytes)
        target_rel = "20_Core/Target.md"
        (vault / target_rel).write_text("target\n", encoding="utf-8")
        envelope = {
            "schema_version": 1,
            "candidate_code": "CR-20260714-000001",
            "candidate_type": "fix_link",
            "source_note_path": source_rel,
            "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "claim": "A claim",
            "target_note_paths": [target_rel],
            "action": {
                "op": "replace", "schema_version": 1,
                "old": "[[Broken]]", "new": "[[20_Core/Target]]",
            },
        }
        runtime = runtime_module.CoreActionRuntime(
            receipt_root=base / "receipts", helper_path=helper,
        )
        setattr(tools, "_RUNTIME", runtime)
        context = FakeContext()
        package.register(context)
        handlers = {item["name"]: item["handler"] for item in context.tools}
        return tools, runtime, base, vault, source_rel, envelope, handlers

    def test_claude_marketplace_versions_match_dual_harness_packages(self):
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entries = {item["name"]: item["version"] for item in marketplace["plugins"]}
        for name in ("donggu-sns", "donggu-obsidian"):
            claude = json.loads(
                (ROOT / name / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
            )
            self.assertEqual(claude["version"], entries[name])
            self.assertEqual(claude["version"], manifest_scalar(ROOT / name / "plugin.yaml", "version"))

    def test_sns_claude_and_hermes_manifests_share_identity_and_version(self):
        package = ROOT / "donggu-sns"
        claude = json.loads((package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hermes = package / "plugin.yaml"
        self.assertEqual("donggu-sns", claude["name"])
        self.assertEqual(claude["name"], manifest_scalar(hermes, "name"))
        self.assertEqual("2.8.0", claude["version"])
        self.assertEqual(claude["version"], manifest_scalar(hermes, "version"))

    def test_codex_marketplace_exposes_only_sns_from_existing_domain_path(self):
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual("donggu-skills", marketplace["name"])
        self.assertEqual("Donggu Skills", marketplace["interface"]["displayName"])
        self.assertEqual(["donggu-sns"], [item["name"] for item in marketplace["plugins"]])
        entry = marketplace["plugins"][0]
        self.assertEqual({"source": "local", "path": "./donggu-sns"}, entry["source"])
        self.assertEqual("2.8.0", entry["version"])
        self.assertEqual(
            {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
            entry["policy"],
        )
        self.assertEqual("Productivity", entry["category"])

    def test_codex_install_docs_name_marketplace_plugin_and_new_thread_boundary(self):
        root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
        sns_readme = (ROOT / "donggu-sns" / "README.md").read_text(encoding="utf-8")
        for text in (root_readme, sns_readme):
            self.assertIn("codex plugin marketplace add donggu1105/donggu-skills", text)
            self.assertIn("codex plugin add donggu-sns@donggu-skills", text)
            self.assertIn("새 thread", text)
        self.assertIn("Hermes", sns_readme)
        self.assertIn("plugin.yaml", sns_readme)
        self.assertIn("Claude Code와 Codex는 같은 `skills/` 트리를 읽고", sns_readme)
        self.assertIn(
            "Hermes `plugin.yaml`은 같은 package root에서 "
            "trusted native publishing tools를 추가로 제공한다",
            sns_readme,
        )
        self.assertIn("실제 mutation은 Hermes에서만 수행한다", sns_readme)
        self.assertIn("codex plugin marketplace upgrade donggu-skills", root_readme)
        self.assertIn(".agents/plugins/marketplace.json", root_readme)
        self.assertIn(".codex-plugin/plugin.json", root_readme)
        self.assertIn("현재 Codex catalog에 미등록", root_readme)
        self.assertNotIn("Claude Code 전용", root_readme)

    def test_sns_codex_manifest_reuses_all_skills_and_matches_release_versions(self):
        package = ROOT / "donggu-sns"
        codex = json.loads(
            (package / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        claude = json.loads(
            (package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual("donggu-sns", codex["name"])
        self.assertEqual("./skills/", codex["skills"])
        self.assertEqual("2.8.0", codex["version"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertEqual(codex["version"], manifest_scalar(package / "plugin.yaml", "version"))
        self.assertEqual(codex["version"], marketplace["plugins"][0]["version"])
        self.assertEqual(
            [
                "get-ai-image",
                "publish-sns",
                "writing-social-content",
                "youtube",
            ],
            sorted(path.parent.name for path in (package / "skills").glob("*/SKILL.md")),
        )

    def test_sns_live_surface_excludes_removed_asset_skills(self):
        package = ROOT / "donggu-sns"
        removed = ("get-stock-image", "make-insta-card-news", "make-shorts")

        for skill_name in removed:
            self.assertFalse((package / "skills" / skill_name).exists())

        live_files = [
            package / "README.md",
            package / ".claude-plugin" / "plugin.json",
            package / ".codex-plugin" / "plugin.json",
        ]
        live_files.extend(
            path
            for path in (package / "skills").rglob("*")
            if path.is_file() and path.suffix in {".md", ".py", ".json", ".yaml", ".yml"}
        )
        for path in live_files:
            text = path.read_text(encoding="utf-8")
            for skill_name in removed:
                with self.subTest(path=path, skill_name=skill_name):
                    self.assertNotIn(skill_name, text)

        claude = json.loads(
            (package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        retired_keywords = {
            "card-news",
            "카드뉴스",
            "stock-image",
            "unsplash",
            "pexels",
            "pixabay",
            "free-image",
        }
        self.assertTrue(retired_keywords.isdisjoint(claude["keywords"]))

        readme = (package / "README.md").read_text(encoding="utf-8")
        self.assertIn("skills-4", readme)
        self.assertIn("사용자 제공 이미지", readme)
        self.assertIn("get-ai-image", readme)

        uploader = package / "skills" / "publish-sns" / "upload_images.py"
        self.assertTrue(uploader.is_file())
        uploader_text = uploader.read_text(encoding="utf-8")
        self.assertIn("SUPABASE_URL", uploader_text)
        self.assertIn("image_urls", uploader_text)
        self.assertNotIn("card-news", uploader_text)

    def test_sns_image_routes_split_instagram_gate_and_prefer_user_assets(self):
        package = ROOT / "donggu-sns"
        publish = (package / "skills" / "publish-sns" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        youtube = (package / "skills" / "youtube" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        with self.subTest(skill="publish-sns"):
            self.assertIn(
                "Threads may publish text-only only after explicit confirmation.", publish
            )
            self.assertIn(
                "If 1–10 finalized image files are absent, STOP", publish
            )
            self.assertIn(
                "obtain user-provided assets first or `get-ai-image` when appropriate, "
                "then rebuild and re-preview",
                publish,
            )
            self.assertIn("Instagram must never publish text-only.", publish)

        with self.subTest(skill="youtube"):
            self.assertIn(
                "사용자 제공 이미지·자산을 먼저 사용한다. 없고 AI 생성이 적절할 때만 "
                "`get-ai-image`를 사용한다.",
                youtube,
            )
            self.assertNotIn("`belt`", youtube)

    def test_sns_publish_image_uploader_preserves_order_and_public_urls(self):
        import contextlib
        import datetime
        import io
        import os
        import runpy

        uploader = ROOT / "donggu-sns" / "skills" / "publish-sns" / "upload_images.py"

        class FixedDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 8, 11, 12, 34, 56)

        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return object()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.png"
            second = root / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            stdout = io.StringIO()
            argv = [
                str(uploader),
                "instagram",
                "launch",
                "sns-media",
                str(first),
                str(second),
            ]
            with mock.patch.dict(
                os.environ,
                {
                    "SUPABASE_URL": "https://example.supabase.co",
                    "SUPABASE_SERVICE_KEY": "secret",
                },
            ), mock.patch("sys.argv", argv), mock.patch(
                "datetime.datetime", FixedDateTime
            ), mock.patch(
                "urllib.request.urlopen", side_effect=fake_urlopen
            ), contextlib.redirect_stdout(stdout):
                runpy.run_path(str(uploader), run_name="__main__")

        payload = json.loads(stdout.getvalue())
        self.assertEqual(2, payload["count"])
        self.assertEqual(
            [
                "https://example.supabase.co/storage/v1/object/public/"
                "sns-media/instagram/2026/08-11/launch-123456/01.png",
                "https://example.supabase.co/storage/v1/object/public/"
                "sns-media/instagram/2026/08-11/launch-123456/02.jpg",
            ],
            payload["image_urls"],
        )
        self.assertEqual([30, 30], [timeout for _, timeout in requests])
        self.assertEqual([b"first", b"second"], [request.data for request, _ in requests])

    def test_sns_publish_image_uploader_rejects_invalid_counts_before_io(self):
        import contextlib
        import io
        import os
        import runpy

        uploader = ROOT / "donggu-sns" / "skills" / "publish-sns" / "upload_images.py"
        expected = ("upload_images.py requires 1–10 image files", 0, 0)

        for count in (0, 11):
            with self.subTest(file_count=count):
                file_open = mock.mock_open()
                file_open.return_value.read.return_value = b"image"
                upload = mock.Mock(return_value=object())
                argv = [
                    str(uploader),
                    "instagram",
                    "launch",
                    "sns-media",
                    *(f"image-{index}.png" for index in range(count)),
                ]
                error = None
                with mock.patch.dict(
                    os.environ,
                    {
                        "SUPABASE_URL": "https://example.supabase.co",
                        "SUPABASE_SERVICE_KEY": "secret",
                    },
                ), mock.patch("sys.argv", argv), mock.patch(
                    "builtins.open", file_open
                ), mock.patch(
                    "urllib.request.urlopen", upload
                ), contextlib.redirect_stdout(io.StringIO()):
                    try:
                        runpy.run_path(str(uploader), run_name="__main__")
                    except SystemExit as exc:
                        error = exc

                self.assertEqual(
                    expected,
                    (
                        None if error is None else str(error),
                        file_open.call_count,
                        upload.call_count,
                    ),
                )

    def test_sns_registers_exact_native_tool_surface(self):
        package = load_package(ROOT / "donggu-sns", "donggu_sns_plugin_test")
        ctx = FakeContext()
        package.register(ctx)
        self.assertEqual(
            [
                "donggu_publishing_preview",
                "donggu_publishing_approve",
                "donggu_publishing_confirm_maily",
                "donggu_publishing_dispatch",
                "donggu_publishing_receipt_status",
            ],
            [item["name"] for item in ctx.tools],
        )
        self.assertTrue(all(item["toolset"] == "donggu_publishing" for item in ctx.tools))
        dispatch = next(item for item in ctx.tools if item["name"] == "donggu_publishing_dispatch")
        approve = next(item for item in ctx.tools if item["name"] == "donggu_publishing_approve")
        confirm = next(item for item in ctx.tools if item["name"] == "donggu_publishing_confirm_maily")
        self.assertEqual(["receipt_id"], approve["schema"]["parameters"]["required"])
        self.assertEqual(["receipt_id"], confirm["schema"]["parameters"]["required"])
        self.assertIn("SNS_WEBHOOK_TOKEN", dispatch["requires_env"])
        self.assertIn("SUPABASE_SERVICE_KEY", dispatch["requires_env"])

    def test_sns_mutation_requires_trusted_hermes_context_and_cli_fails_closed(self):
        module_name = "donggu_sns_security_contract_test"
        package = load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(module_name + ".tools")
        with self.assertRaises(tools.PublishingError):
            tools._trusted_context({})
        self.assertEqual(
            ("session", "session:task:turn-2"),
            tools._trusted_context({"session_id": "session", "turn_id": "session:task:turn-2"}),
        )

        cli = importlib.import_module(module_name + ".runtime.publishing_cli")
        for action in ("approve", "confirm_maily", "dispatch"):
            with self.assertRaises(cli.PublishingError):
                cli.execute({"action": action, "receipt_id": "receipt"}, object())

    def test_sns_handler_uses_session_db_message_and_singleton_is_thread_safe(self):
        module_name = "donggu_sns_thread_contract_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(module_name + ".tools")

        class FakeRuntime:
            def __init__(self):
                self.approval_text = None

            def approve(
                self, receipt_id, *, approval_text, session_id, turn_id,
                user_message_id, authoritative_claim_executor,
            ):
                authoritative_claim_executor(lambda: None)
                self.approval_text = approval_text
                self.user_message_id = user_message_id
                return {"status": "approved", "receipt_id": receipt_id}

        fake = FakeRuntime()
        setattr(tools, "_RUNTIME", fake)
        with mock.patch.object(
            tools, "_latest_trusted_user_message", return_value=(2, "[강동현] 승인"),
        ), mock.patch.object(
            tools,
            "_authoritative_latest_message_executor",
            return_value=lambda action: action(),
        ):
            result = json.loads(tools.handle_approve(
                {"receipt_id": "receipt"}, session_id="session", turn_id="turn-2",
            ))
        self.assertTrue(result["success"])
        self.assertEqual("[강동현] 승인", fake.approval_text)
        self.assertEqual(2, fake.user_message_id)

        setattr(tools, "_RUNTIME", None)
        created = []

        def create_runtime():
            time.sleep(0.03)
            value = object()
            created.append(value)
            return value

        results = []
        with mock.patch.object(tools.PublishingRuntime, "from_env", side_effect=create_runtime):
            threads = [threading.Thread(target=lambda: results.append(tools._runtime())) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(1, len(created))
        self.assertEqual(1, len({id(value) for value in results}))

    def test_sns_latest_user_lookup_fails_closed_on_blank_latest_row(self):
        module_name = "donggu_sns_blank_latest_message_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(f"{module_name}.tools")

        class FakeSessionDB:
            def get_messages(self, _session_id):
                return [
                    {"id": 1, "role": "user", "content": "블로그 업데이트 적용해줘"},
                    {"id": 2, "role": "assistant", "content": "working"},
                    {"id": 3, "role": "user", "content": ""},
                ]

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            with self.assertRaises(tools.PublishingError):
                tools._latest_trusted_user_message("session")

    def test_sns_latest_user_lookup_fails_closed_on_structured_latest_row(self):
        module_name = "donggu_sns_structured_latest_message_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(f"{module_name}.tools")

        class FakeSessionDB:
            def get_messages(self, _session_id):
                return [
                    {"id": 1, "role": "user", "content": "블로그 업데이트 적용해줘"},
                    {"id": 2, "role": "user", "content": [{"type": "text", "text": "취소"}]},
                ]

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            with self.assertRaises(tools.PublishingError):
                tools._latest_trusted_user_message("session")

    def test_sns_latest_user_lookup_fails_closed_on_invalid_latest_row_id(self):
        module_name = "donggu_sns_invalid_latest_message_id_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(f"{module_name}.tools")

        class FakeSessionDB:
            def get_messages(self, _session_id):
                return [
                    {"id": 1, "role": "user", "content": "블로그 업데이트 적용해줘"},
                    {"id": None, "role": "user", "content": "취소"},
                ]

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            with self.assertRaises(tools.PublishingError):
                tools._latest_trusted_user_message("session")

    def test_sns_approve_and_confirm_revalidate_latest_message_inside_claim(self):
        module_name = "donggu_sns_claim_revalidation_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(f"{module_name}.tools")

        class FakeRuntime:
            def approve(self, _receipt_id, *, authoritative_claim_executor=None, **_kwargs):
                self.assert_executor(authoritative_claim_executor)

            def confirm_irreversible(
                self, _receipt_id, *, authoritative_claim_executor=None, **_kwargs,
            ):
                self.assert_executor(authoritative_claim_executor)

            @staticmethod
            def assert_executor(executor):
                if executor is None:
                    raise AssertionError("authoritative executor was not provided")
                executor(lambda: None)

        setattr(tools, "_RUNTIME", FakeRuntime())
        cases = (
            (tools.handle_approve, "블로그 업데이트 적용해줘"),
            (tools.handle_confirm, "메일 최종 발송 확인"),
        )
        for handler, authorization_text in cases:
            with self.subTest(handler=handler.__name__):
                def reject_stale_claim(_action):
                    raise tools.PublishingError(
                        "trusted Hermes user message changed before authorization claim"
                    )

                with mock.patch.object(
                    tools,
                    "_latest_trusted_user_message",
                    return_value=(2, authorization_text),
                ) as latest:
                    with mock.patch.object(
                        tools,
                        "_authoritative_latest_message_executor",
                        return_value=reject_stale_claim,
                    ):
                        result = json.loads(handler(
                            {"receipt_id": "receipt"},
                            session_id="session", turn_id="turn-2",
                        ))
                self.assertFalse(result["success"])
                self.assertEqual(1, latest.call_count)

    def test_sns_authoritative_executor_runs_claim_under_sessiondb_write_lock(self):
        module_name = "donggu_sns_claim_db_lock_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(f"{module_name}.tools")

        class FakeCursor:
            def fetchone(self):
                return {"id": 2, "content": "블로그 업데이트 적용해줘"}

        class FakeConnection:
            def execute(self, sql, params):
                self.sql = sql
                self.params = params
                return FakeCursor()

        class FakeSessionDB:
            instance = None

            def __init__(self):
                self.write_locked = False
                self.closed = False
                FakeSessionDB.instance = self

            def _decode_content(self, content):
                return content

            def _execute_write(self, callback):
                self.write_locked = True
                try:
                    return callback(FakeConnection())
                finally:
                    self.write_locked = False

            def close(self):
                self.closed = True

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        claimed = []

        def claim():
            instance = FakeSessionDB.instance
            assert instance is not None
            self.assertTrue(instance.write_locked)
            claimed.append("claimed")
            return {"state": "approved"}

        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            result = tools._authoritative_latest_message_executor(
                "session", 2, "블로그 업데이트 적용해줘",
            )(claim)
        self.assertEqual({"state": "approved"}, result)
        self.assertEqual(["claimed"], claimed)
        instance = FakeSessionDB.instance
        assert instance is not None
        self.assertTrue(instance.closed)

    def test_sns_authoritative_executor_rejects_newer_user_row_before_claim(self):
        module_name = "donggu_sns_claim_db_stale_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(f"{module_name}.tools")

        class FakeCursor:
            def fetchone(self):
                return {"id": 3, "content": "취소"}

        class FakeConnection:
            def execute(self, _sql, _params):
                return FakeCursor()

        class FakeSessionDB:
            def _decode_content(self, content):
                return content

            def _execute_write(self, callback):
                return callback(FakeConnection())

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        claimed = []
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            executor = tools._authoritative_latest_message_executor(
                "session", 2, "블로그 업데이트 적용해줘",
            )
            with self.assertRaises(tools.PublishingError):
                executor(lambda: claimed.append("claimed"))
        self.assertEqual([], claimed)

    def test_obsidian_runtime_singleton_is_thread_safe(self):
        module_name = "donggu_obsidian_thread_contract_test"
        load_package(ROOT / "donggu-obsidian", module_name)
        tools = importlib.import_module(module_name + ".tools")
        setattr(tools, "_RUNTIME", None)
        created = []

        def create_runtime():
            time.sleep(0.03)
            value = object()
            created.append(value)
            return value

        results = []
        with mock.patch.object(tools.CoreActionRuntime, "from_package", side_effect=create_runtime):
            threads = [threading.Thread(target=lambda: results.append(tools._runtime())) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(1, len(created))
        self.assertEqual(1, len({id(value) for value in results}))

    def test_obsidian_claude_and_hermes_manifests_share_identity_and_version(self):
        package = ROOT / "donggu-obsidian"
        claude = json.loads((package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hermes = package / "plugin.yaml"
        self.assertEqual("donggu-obsidian", claude["name"])
        self.assertEqual(claude["name"], manifest_scalar(hermes, "name"))
        self.assertEqual("2.1.0", claude["version"])
        self.assertEqual(claude["version"], manifest_scalar(hermes, "version"))

    def test_obsidian_latest_user_lookup_reads_past_first_fifty_messages(self):
        module_name = "donggu_obsidian_latest_message_test"
        load_package(ROOT / "donggu-obsidian", module_name)
        tools = importlib.import_module(f"{module_name}.tools")
        messages = [
            {"id": index, "role": "user", "content": "CR-20260713-000001 승인" if index == 1 else f"message-{index}"}
            for index in range(1, 61)
        ]

        class FakeSessionDB:
            def get_messages(self, _session_id, limit=None):
                return messages if limit is None else messages[:limit]

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            message_id, text = tools._latest_trusted_user_message("session")
        self.assertEqual(60, message_id)
        self.assertEqual("message-60", text)

    def test_obsidian_latest_user_lookup_does_not_fall_back_past_blank_latest_row(self):
        module_name = "donggu_obsidian_blank_latest_message_test"
        load_package(ROOT / "donggu-obsidian", module_name)
        tools = importlib.import_module(f"{module_name}.tools")
        messages = [
            {"id": 1, "role": "user", "content": "적용해줘"},
            {"id": 2, "role": "assistant", "content": "working"},
            {"id": 3, "role": "user", "content": ""},
        ]

        class FakeSessionDB:
            def get_messages(self, _session_id, limit=None):
                return messages

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            message_id, text = tools._latest_trusted_user_message("session")
        self.assertEqual(3, message_id)
        self.assertEqual("", text)

    def test_obsidian_latest_user_lookup_fails_closed_on_structured_latest_row(self):
        module_name = "donggu_obsidian_structured_latest_message_test"
        load_package(ROOT / "donggu-obsidian", module_name)
        tools = importlib.import_module(f"{module_name}.tools")

        class FakeSessionDB:
            def get_messages(self, _session_id, limit=None):
                return [
                    {"id": 1, "role": "user", "content": "적용해줘"},
                    {"id": 2, "role": "user", "content": [{"type": "text", "text": "other"}]},
                ]

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            with self.assertRaises(tools.CoreRuntimeError):
                tools._latest_trusted_user_message("session")

    def test_obsidian_registers_exact_native_tool_surface(self):
        package = load_package(ROOT / "donggu-obsidian", "donggu_obsidian_plugin_test")
        ctx = FakeContext()
        package.register(ctx)
        self.assertEqual(
            [
                "donggu_core_recovery_status",
                "donggu_core_plan",
                "donggu_core_receipt_status",
                "donggu_core_apply",
                "donggu_core_recover",
                "donggu_core_readback",
                "donggu_core_revoke",
                "donggu_core_ack",
                "donggu_life_os_status",
                "donggu_life_os_start_daily",
                "donggu_life_os_record",
                "donggu_life_os_finalize_daily",
            ],
            [item["name"] for item in ctx.tools],
        )
        by_name = {item["name"]: item for item in ctx.tools}
        self.assertEqual(
            ["vault_root", "envelope"],
            by_name["donggu_core_plan"]["schema"]["parameters"]["required"],
        )
        for name in (
            "donggu_core_receipt_status", "donggu_core_apply", "donggu_core_readback",
            "donggu_core_recover", "donggu_core_revoke",
        ):
            self.assertEqual(["receipt_id"], by_name[name]["schema"]["parameters"]["required"])
            self.assertEqual({"receipt_id"}, set(by_name[name]["schema"]["parameters"]["properties"]))
        ack_parameters = by_name["donggu_core_ack"]["schema"]["parameters"]
        self.assertEqual(["receipt_id", "completion_nonce"], ack_parameters["required"])
        self.assertEqual({"receipt_id", "completion_nonce"}, set(ack_parameters["properties"]))
        self.assertTrue(all(item["toolset"] == "donggu_obsidian" for item in ctx.tools))
        manifest_tools = re.findall(
            r"(?m)^  - (donggu_(?:core|life_os)_[a-z_]+)$",
            (ROOT / "donggu-obsidian" / "plugin.yaml").read_text(encoding="utf-8"),
        )
        self.assertEqual([item["name"] for item in ctx.tools], manifest_tools)
        self.assertEqual(12, len(manifest_tools))

    def test_registered_obsidian_apply_reads_latest_natural_text_and_reaches_real_helper_once(self):
        module_name = "donggu_obsidian_registered_apply_test"
        package = load_package(ROOT / "donggu-obsidian", module_name)
        tools = importlib.import_module(module_name + ".tools")
        runtime_module = importlib.import_module(module_name + ".runtime")
        helper = ROOT / "donggu-obsidian" / "skills" / "core-review-approval" / "scripts" / "apply-action.py"

        import hashlib
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            vault = base / "vault"
            for name in ("10_Sources", "20_Core", "40_Channel_Packs", "50_MOCs"):
                (vault / name).mkdir(parents=True)
            source_rel = "10_Sources/source.md"
            source_bytes = b"---\ntype: source\nextracted_to: []\n---\n\n[[Broken]]\n"
            (vault / source_rel).write_bytes(source_bytes)
            target_rel = "20_Core/Target.md"
            (vault / target_rel).write_text("target\n", encoding="utf-8")
            envelope = {
                "schema_version": 1,
                "candidate_code": "CR-20260714-000001",
                "candidate_type": "fix_link",
                "source_note_path": source_rel,
                "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
                "claim": "A claim",
                "target_note_paths": [target_rel],
                "action": {
                    "op": "replace", "schema_version": 1,
                    "old": "[[Broken]]", "new": "[[20_Core/Target]]",
                },
            }
            runtime = runtime_module.CoreActionRuntime(
                receipt_root=base / "receipts", helper_path=helper,
            )
            setattr(tools, "_RUNTIME", runtime)
            ctx = FakeContext()
            package.register(ctx)
            apply_handler = next(item["handler"] for item in ctx.tools if item["name"] == "donggu_core_apply")
            plan_handler = next(item["handler"] for item in ctx.tools if item["name"] == "donggu_core_plan")
            original_run = runtime._run
            mutation_calls = []

            def capture(root, candidate_envelope, *flags):
                if candidate_envelope is not None and not flags:
                    mutation_calls.append(candidate_envelope["candidate_code"])
                return original_run(root, candidate_envelope, *flags)

            rows = {
                "persisted-session": [{"id": 1, "role": "user", "content": "수정안 보여줘"}],
                "other-session": [{"id": 3, "role": "user", "content": "적용해줘"}],
            }

            class FakeSessionDB:
                def get_messages(self, session_id, limit=None):
                    return list(rows.get(session_id, []))

                def close(self):
                    return None

            fake_module = types.ModuleType("hermes_state")
            setattr(fake_module, "SessionDB", FakeSessionDB)
            with mock.patch.dict(sys.modules, {"hermes_state": fake_module}), mock.patch.object(
                runtime, "_run", side_effect=capture
            ):
                first_plan = json.loads(plan_handler(
                    {"vault_root": str(vault), "envelope": envelope}, session_id="persisted-session",
                ))
                second_plan = json.loads(plan_handler(
                    {"vault_root": str(vault), "envelope": envelope}, session_id="persisted-session",
                ))
                self.assertTrue(first_plan["success"] and second_plan["success"])
                rows["persisted-session"].append({"id": 2, "role": "user", "content": "적용해줘"})
                cross_session = json.loads(apply_handler(
                    {"receipt_id": first_plan["receipt_id"]}, session_id="other-session",
                ))
                self.assertFalse(cross_session["success"])
                payload = json.loads(apply_handler(
                    {"receipt_id": first_plan["receipt_id"]}, session_id="persisted-session",
                ))
                reused = json.loads(apply_handler(
                    {"receipt_id": second_plan["receipt_id"]}, session_id="persisted-session",
                ))
            self.assertFalse(reused["success"])
            self.assertTrue(payload["success"])
            self.assertEqual("vault_committed_reconciliation_required", payload["status"])
            self.assertEqual(["CR-20260714-000001"], mutation_calls)
            self.assertIn("[[20_Core/Target]]", (vault / source_rel).read_text(encoding="utf-8"))

    def test_registered_obsidian_plan_revokes_receipt_when_latest_row_overtakes_dry_run(self):
        _tools, runtime, base, vault, _source_rel, envelope, handlers = self.registered_obsidian_fixture(
            "donggu_obsidian_registered_plan_overtake_test"
        )
        rows = [{"id": 1, "role": "user", "content": "수정안 보여줘"}]

        class FakeSessionDB:
            def get_messages(self, _session_id, limit=None):
                return list(rows)

            def close(self):
                return None

        original_run = runtime._run

        def overtake_dry_run(root, candidate_envelope, *flags):
            result = original_run(root, candidate_envelope, *flags)
            if "--dry-run" in flags:
                rows.append({"id": 2, "role": "user", "content": "적용해줘"})
            return result

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}), mock.patch.object(
            runtime, "_run", side_effect=overtake_dry_run
        ):
            payload = json.loads(handlers["donggu_core_plan"](
                {"vault_root": str(vault), "envelope": envelope}, session_id="persisted-session",
            ))

        self.assertFalse(payload["success"])
        receipts = list((base / "receipts").glob("*.json"))
        self.assertEqual(1, len(receipts))
        receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
        self.assertEqual("revoked", receipt["state"])
        self.assertIsNone(receipt["envelope"])

    def test_registered_obsidian_apply_rejects_newer_cancel_at_local_claim_boundary(self):
        _tools, runtime, _base, vault, source_rel, envelope, handlers = self.registered_obsidian_fixture(
            "donggu_obsidian_registered_apply_overtake_test"
        )
        rows = [{"id": 1, "role": "user", "content": "수정안 보여줘"}]

        class FakeSessionDB:
            def get_messages(self, _session_id, limit=None):
                return list(rows)

            def close(self):
                return None

        fake_module = types.ModuleType("hermes_state")
        setattr(fake_module, "SessionDB", FakeSessionDB)
        original_binding = runtime._validate_receipt_binding
        original_run = runtime._run
        mutation_calls = []

        def overtake_validation(receipt):
            original_binding(receipt)
            rows.append({"id": 3, "role": "user", "content": "취소"})

        def capture_helper(root, candidate_envelope, *flags):
            if candidate_envelope is not None and not flags:
                mutation_calls.append(candidate_envelope["candidate_code"])
            return original_run(root, candidate_envelope, *flags)

        with mock.patch.dict(sys.modules, {"hermes_state": fake_module}):
            plan = json.loads(handlers["donggu_core_plan"](
                {"vault_root": str(vault), "envelope": envelope}, session_id="persisted-session",
            ))
            self.assertTrue(plan["success"])
            rows.append({"id": 2, "role": "user", "content": "적용해줘"})
            with mock.patch.object(
                runtime, "_validate_receipt_binding", side_effect=overtake_validation
            ), mock.patch.object(runtime, "_run", side_effect=capture_helper):
                payload = json.loads(handlers["donggu_core_apply"](
                    {"receipt_id": plan["receipt_id"]}, session_id="persisted-session",
                ))

        self.assertFalse(payload["success"])
        self.assertEqual([], mutation_calls)
        self.assertNotIn("[[20_Core/Target]]", (vault / source_rel).read_text(encoding="utf-8"))
        self.assertEqual("planned", runtime.store.load(plan["receipt_id"])["state"])


if __name__ == "__main__":
    unittest.main()
