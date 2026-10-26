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

    def test_claude_marketplace_versions_match_dual_harness_packages(self):
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        )
        entries = {item["name"]: item["version"] for item in marketplace["plugins"]}
        for name in ("donggu-sns",):
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
        self.assertEqual("2.14.0", claude["version"])
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
        self.assertEqual("2.14.0", entry["version"])
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
        self.assertEqual("2.14.0", codex["version"])
        self.assertEqual(codex["version"], claude["version"])
        self.assertEqual(codex["version"], manifest_scalar(package / "plugin.yaml", "version"))
        self.assertEqual(codex["version"], marketplace["plugins"][0]["version"])
        self.assertEqual(
            [
                "decompose-canon",
                "extract-core",
                "get-ai-image",
                "make-card-news",
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
            "stock-image",
            "unsplash",
            "pexels",
            "pixabay",
            "free-image",
        }
        self.assertTrue(retired_keywords.isdisjoint(claude["keywords"]))

        readme = (package / "README.md").read_text(encoding="utf-8")
        self.assertIn("skills-7", readme)
        self.assertIn("사용자 제공 이미지", readme)
        self.assertIn("get-ai-image", readme)

        uploader = package / "skills" / "publish-sns" / "upload_images.py"
        self.assertTrue(uploader.is_file())
        uploader_text = uploader.read_text(encoding="utf-8")
        self.assertIn("SUPABASE_URL", uploader_text)
        self.assertIn("image_urls", uploader_text)
        self.assertNotIn("make-insta-card-news", uploader_text)

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
                "donggu_publishing_execute",
                "donggu_publishing_receipt_status",
                "donggu_publishing_list_reconciliations",
                "donggu_publishing_resolve_reconciliation",
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
        self.assertIn("PUBLISHER_API_TOKEN", dispatch["requires_env"])
        self.assertIn("SUPABASE_SERVICE_KEY", dispatch["requires_env"])

    def test_sns_approval_strips_headerless_discord_sender_label_safely(self):
        """Regression 2026-10-22: Hermes stopped persisting the Triggering header,
        so '[강동현] 티스토리 발행해' was rejected. Strip a plain sender label, but
        never one that carries steering text, and never on multi-line rows."""
        module_name = "donggu_sns_headerless_label_test"
        load_package(ROOT / "donggu-sns", module_name)
        tools = importlib.import_module(module_name + ".tools")
        runtime_mod = importlib.import_module(module_name + ".runtime.publishing")
        normalize = tools._normalize_trusted_user_message
        approve = runtime_mod._require_operation_approval

        # header-less single-line rows: label removed, grammar still enforced
        self.assertEqual("티스토리 발행해", normalize("[강동현] 티스토리 발행해"))
        self.assertEqual("티스토리 발행해", approve(normalize("[강동현] 티스토리 발행해"), "publish"))
        self.assertEqual("스레드 발행해", normalize("[강동현]스레드 발행해"))
        # legacy header form still works
        self.assertEqual(
            "발행해",
            normalize("[Triggering message id: `1` — use as `message_id`]\n\n[강동현] 발행해"),
        )
        # a label carrying steering text is NOT stripped, so approval fails
        for row in ("[하지 마] 발행해", "[취소] 발행해", "[나중에] 발행해", "[이거 맞아?] 발행해"):
            with self.subTest(row=row):
                self.assertEqual(row, normalize(row))
                with self.assertRaises(runtime_mod.ApprovalError):
                    approve(normalize(row), "publish")
        # multi-line rows (context blocks, injected notices) are never label-stripped
        block = "[Recent channel messages]\n[강동현] 아직도?\n\n[New message]\n[강동현] 발행해"
        self.assertEqual(block, normalize(block))
        with self.assertRaises(runtime_mod.ApprovalError):
            approve(normalize(block), "publish")
        # stripping the label never turns a non-approval into an approval
        for row in ("[강동현] 발행해 볼까?", "[강동현] 발행해 두지 마", "[강동현] 응"):
            with self.subTest(row=row), self.assertRaises(runtime_mod.ApprovalError):
                approve(normalize(row), "publish")

    def _assert_host_context_via_public_middleware(self, package, tools):
        """Turn ID must arrive through the documented tool_execution middleware,
        never through a Hermes-internal import (broke silently on 2026-09 refactor)."""
        middleware = []

        class MiddlewareContext(FakeContext):
            def register_middleware(self, kind, callback):
                middleware.append((kind, callback))

        package.register(MiddlewareContext())
        self.assertEqual(["tool_execution"], [kind for kind, _ in middleware])
        bind = middleware[0][1]
        seen = []

        def handler(args):
            seen.append(tools._trusted_context({"session_id": "s1"}))
            return "ok"

        result = bind(tool_name="donggu_publishing_preview", args={}, next_call=handler,
                      session_id="s1", turn_id="s1:turn-7", task_id="t", tool_call_id="c")
        self.assertEqual("ok", result)
        self.assertEqual([("s1", "s1:turn-7")], seen)
        # context does not leak past the call
        with self.assertRaises(tools.PublishingError):
            tools._trusted_context({"session_id": "s1"})
        # mismatched session fails closed
        with self.assertRaises(tools.PublishingError):
            bind(tool_name="donggu_publishing_preview", args={},
                 next_call=lambda a: tools._trusted_context({"session_id": "other"}),
                 session_id="s1", turn_id="s1:turn-7")
        # other tools pass through without binding
        bind(tool_name="terminal", args={}, next_call=lambda a: seen.append(tools._HOST_CALL_CONTEXT.get()),
             session_id="s1", turn_id="s1:turn-8")
        self.assertEqual(("", ""), seen[-1])
        # source must not reach into Hermes internals
        source = (ROOT / "donggu-sns" / "tools.py").read_text(encoding="utf-8")
        self.assertNotIn("from tools.approval", source)

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
        self._assert_host_context_via_public_middleware(package, tools)

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

if __name__ == "__main__":
    unittest.main()
