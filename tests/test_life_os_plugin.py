#!/usr/bin/env python3
from datetime import date
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]


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

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_hook(self, name, callback):
        self.hooks.append((name, callback))


class LifeOSPluginTests(unittest.TestCase):
    def setUp(self):
        self.module_name = f"life_os_plugin_test_{self._testMethodName}"
        self.package = load_package(ROOT / "donggu-obsidian", self.module_name)
        self.tools = importlib.import_module(self.module_name + ".tools")
        if hasattr(self.tools, "_TRUSTED_TURNS"):
            self.tools._TRUSTED_TURNS.clear()
        self.hermes_config = {
            "discord": {
                "channel_skill_bindings": [{"id": "456", "skill": "life-os"}],
            },
        }
        hermes_cli = types.ModuleType("hermes_cli")
        hermes_cli.__path__ = []
        gateway = types.ModuleType("gateway")
        gateway.__path__ = []
        self._default_modules = mock.patch.dict(sys.modules, {
            "hermes_cli": hermes_cli,
            "hermes_cli.config": types.SimpleNamespace(
                load_config_readonly=lambda: self.hermes_config,
            ),
            "gateway": gateway,
            "gateway.session_context": types.SimpleNamespace(
                get_session_env=self.session_context(),
            ),
        })
        self._default_modules.start()
        self.addCleanup(self._default_modules.stop)

    @staticmethod
    def discord_event(
        *, text="오늘 산책했어", event_text=None, message_type="text",
        media_urls=(), media_types=(), message_id="123", chat_id="456", user_id="789",
    ):
        class FakeDiscordMessage:
            pass

        raw = FakeDiscordMessage()
        raw.content = text
        raw.id = int(message_id)
        raw.channel = types.SimpleNamespace(id=int(chat_id))
        raw.author = types.SimpleNamespace(id=int(user_id), bot=False)
        source = types.SimpleNamespace(
            platform=types.SimpleNamespace(value="discord"),
            chat_id=chat_id,
            user_id=user_id,
            thread_id=None,
            profile=None,
            message_id=message_id,
            is_bot=False,
        )
        event = types.SimpleNamespace(
            raw_message=raw,
            source=source,
            message_id=message_id,
            text=text.strip() if event_text is None else event_text,
            message_type=types.SimpleNamespace(value=message_type),
            media_urls=list(media_urls),
            media_types=list(media_types),
        )
        return FakeDiscordMessage, event

    @staticmethod
    def session_context(
        *, platform="discord", message_id="123", chat_id="456", user_id="789",
        session_id="session-1",
    ):
        values = {
            "HERMES_SESSION_PLATFORM": platform,
            "HERMES_SESSION_CHAT_ID": chat_id,
            "HERMES_SESSION_USER_ID": user_id,
            "HERMES_SESSION_THREAD_ID": "",
            "HERMES_SESSION_PROFILE": "",
            "HERMES_SESSION_MESSAGE_ID": message_id,
            "HERMES_SESSION_ID": session_id,
            "HERMES_SESSION_KEY": "agent:main:discord:456:789",
            "HERMES_CRON_SESSION": "",
            "HERMES_CRON_AUTO_DELIVER_PLATFORM": "",
            "HERMES_CRON_AUTO_DELIVER_CHAT_ID": "",
        }
        return lambda name, default="": values.get(name, default)

    @staticmethod
    def cron_context(*, marker="1", platform="discord", chat_id="456"):
        values = {
            "HERMES_SESSION_PLATFORM": "",
            "HERMES_SESSION_SOURCE": "",
            "HERMES_SESSION_CHAT_ID": "",
            "HERMES_SESSION_CHAT_TYPE": "",
            "HERMES_SESSION_CHAT_NAME": "",
            "HERMES_SESSION_THREAD_ID": "",
            "HERMES_SESSION_USER_ID": "",
            "HERMES_SESSION_USER_NAME": "",
            "HERMES_SESSION_KEY": "",
            "HERMES_SESSION_ID": "",
            "HERMES_UI_SESSION_ID": "",
            "HERMES_SESSION_MESSAGE_ID": "",
            "HERMES_SESSION_PROFILE": "",
            "HERMES_CRON_SESSION": marker,
            "HERMES_CRON_AUTO_DELIVER_PLATFORM": platform,
            "HERMES_CRON_AUTO_DELIVER_CHAT_ID": chat_id,
        }
        return lambda name, default="": values.get(name, default)

    @staticmethod
    def gateway(session_key="agent:main:discord:456:789"):
        return types.SimpleNamespace(_session_key_for_source=lambda _source: session_key)

    def test_life_os_schemas_are_strict(self):
        date_property = {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
        }
        for schema in (
            self.tools.LIFE_OS_STATUS_SCHEMA,
            self.tools.LIFE_OS_START_DAILY_SCHEMA,
        ):
            parameters = schema["parameters"]
            self.assertEqual("object", parameters["type"])
            self.assertEqual({"date": date_property}, parameters["properties"])
            self.assertNotIn("required", parameters)
            self.assertIs(False, parameters["additionalProperties"])

        record = self.tools.LIFE_OS_RECORD_SCHEMA
        self.assertEqual("donggu_life_os_record", record["name"])
        self.assertEqual(
            {
                "operation": {
                    "type": "string",
                    "enum": ["answer", "skip", "pause", "resume", "capture", "free_record"],
                },
                "date": date_property,
                "follow_up_question": {"type": "string", "minLength": 1, "maxLength": 300},
                "attachment_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 10,
                },
            },
            record["parameters"]["properties"],
        )
        self.assertEqual(["operation"], record["parameters"]["required"])
        self.assertIs(False, record["parameters"]["additionalProperties"])

    def test_life_os_tools_register_after_existing_core_surface(self):
        ctx = FakeContext()
        self.package.register(ctx)
        self.assertEqual(
            [
                "donggu_core_recovery_status", "donggu_core_plan",
                "donggu_core_receipt_status", "donggu_core_apply",
                "donggu_core_recover", "donggu_core_readback",
                "donggu_core_revoke", "donggu_core_ack",
                "donggu_life_os_status", "donggu_life_os_start_daily",
                "donggu_life_os_record",
            ],
            [item["name"] for item in ctx.tools],
        )
        self.assertTrue(all(item["toolset"] == "donggu_obsidian" for item in ctx.tools))
        self.assertEqual(["pre_gateway_dispatch"], [name for name, _callback in ctx.hooks])
        manifest = (ROOT / "donggu-obsidian" / "plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("provides_hooks:\n  - pre_gateway_dispatch", manifest)

    def test_status_and_start_handlers_accept_an_optional_iso_date_without_session_db(self):
        runtime = mock.Mock()
        runtime.status.return_value = {"status": "active"}
        runtime.start_daily.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)

        with mock.patch.object(
            self.tools, "_latest_trusted_user_message",
            side_effect=AssertionError("status/start must not read SessionDB"),
        ):
            status = json.loads(self.tools.handle_life_os_status({"date": "2026-08-07"}))
            started = json.loads(self.tools.handle_life_os_start_daily({}))

        self.assertTrue(status["success"])
        self.assertTrue(started["success"])
        runtime.status.assert_called_once_with(date(2026, 8, 7))
        runtime.start_daily.assert_called_once_with(None, resume=True)

    def test_origin_guard_rejects_wrong_discord_channel_for_hook_and_all_handlers(self):
        runtime = mock.Mock()
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event(chat_id="999")
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 25, "role": "user", "content": "prepared"}]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            record = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(record["success"])

        wrong_context = types.SimpleNamespace(
            get_session_env=self.session_context(chat_id="999"),
        )
        with mock.patch.dict(sys.modules, {"gateway.session_context": wrong_context}):
            status = json.loads(self.tools.handle_life_os_status({}))
            start = json.loads(self.tools.handle_life_os_start_daily({}))
            wrong_record = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(status["success"])
        self.assertFalse(start["success"])
        self.assertFalse(wrong_record["success"])
        runtime.status.assert_not_called()
        runtime.start_daily.assert_not_called()
        runtime.record.assert_not_called()

    def test_origin_guard_allows_only_exact_cron_start_delivery(self):
        runtime = mock.Mock()
        runtime.start_daily.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        with mock.patch.dict(sys.modules, {
            "gateway.session_context": types.SimpleNamespace(
                get_session_env=self.cron_context(),
            ),
        }):
            allowed = json.loads(self.tools.handle_life_os_start_daily({}))
            denied_status = json.loads(self.tools.handle_life_os_status({}))
            denied_record = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertTrue(allowed["success"])
        self.assertFalse(denied_status["success"])
        self.assertFalse(denied_record["success"])
        runtime.start_daily.assert_called_once_with(None, resume=True)
        runtime.status.assert_not_called()
        runtime.record.assert_not_called()

        for context in (
            self.cron_context(marker="true"),
            self.cron_context(platform="slack"),
            self.cron_context(chat_id="999"),
        ):
            with self.subTest(context=context):
                runtime.reset_mock()
                with mock.patch.dict(sys.modules, {
                    "gateway.session_context": types.SimpleNamespace(get_session_env=context),
                }):
                    denied = json.loads(self.tools.handle_life_os_start_daily({}))
                self.assertFalse(denied["success"])
                runtime.start_daily.assert_not_called()

        live_identity_names = (
            "HERMES_SESSION_PLATFORM", "HERMES_SESSION_SOURCE",
            "HERMES_SESSION_CHAT_ID", "HERMES_SESSION_CHAT_TYPE",
            "HERMES_SESSION_CHAT_NAME", "HERMES_SESSION_THREAD_ID",
            "HERMES_SESSION_USER_ID", "HERMES_SESSION_USER_NAME",
            "HERMES_SESSION_KEY", "HERMES_SESSION_ID", "HERMES_UI_SESSION_ID",
            "HERMES_SESSION_MESSAGE_ID", "HERMES_SESSION_PROFILE",
        )
        for contaminated_name in live_identity_names:
            with self.subTest(contaminated_name=contaminated_name):
                runtime.reset_mock()
                cron = self.cron_context()
                mixed_context = lambda name, default="", target=contaminated_name: (
                    "contaminated" if name == target else cron(name, default)
                )
                with mock.patch.dict(sys.modules, {
                    "gateway.session_context": types.SimpleNamespace(get_session_env=mixed_context),
                }):
                    denied = json.loads(self.tools.handle_life_os_start_daily({}))
                self.assertFalse(denied["success"])
                runtime.start_daily.assert_not_called()

    def test_origin_guard_rejects_invalid_and_duplicate_life_os_bindings(self):
        runtime = mock.Mock()
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        invalid_bindings = (
            "not-a-list",
            [{"id": "456", "skill": "life-os"}, {"id": "456", "skill": "other"}],
            [{"id": "456", "skill": "life-os"}, {"id": "999", "skill": "life-os"}],
            [{"id": "456", "skills": ["life-os", "other"]}],
        )
        for bindings in invalid_bindings:
            with self.subTest(bindings=bindings):
                self.hermes_config["discord"]["channel_skill_bindings"] = bindings
                denied = json.loads(self.tools.handle_life_os_start_daily({}))
                self.assertFalse(denied["success"])
        for config in (None, [], {"discord": None}):
            with self.subTest(config=config):
                self.hermes_config = config
                denied = json.loads(self.tools.handle_life_os_start_daily({}))
                self.assertFalse(denied["success"])
        runtime.start_daily.assert_not_called()

    def test_origin_guard_accepts_exact_single_item_skills_binding(self):
        runtime = mock.Mock()
        runtime.status.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        self.hermes_config["discord"]["channel_skill_bindings"] = [
            {"id": "456", "skills": ["life-os"]},
        ]
        result = json.loads(self.tools.handle_life_os_status({}))
        self.assertTrue(result["success"])
        runtime.status.assert_called_once_with(None)

    def test_cron_start_resumes_a_paused_daily(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            vault = base / "vault"
            template = vault / "Life OS/0. PeriodicNotes/Templates/Daily.md"
            template.parent.mkdir(parents=True)
            template.write_text("## Daily Record\n%%Your Record%%\n", encoding="utf-8")
            runtime = self.tools.LifeOSRuntime(
                vault_root=vault,
                state_root=base / "state",
                timezone=ZoneInfo("Asia/Seoul"),
                cache_roots=(),
                max_attachment_bytes=1024,
            )
            day = date(2026, 8, 7)
            runtime.start_daily(day)
            runtime.record("pause", message_text="그만", message_key="cron:pause", target_date=day)
            setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
            with mock.patch.dict(sys.modules, {
                "gateway.session_context": types.SimpleNamespace(
                    get_session_env=self.cron_context(),
                ),
            }):
                result = json.loads(self.tools.handle_life_os_start_daily({"date": "2026-08-07"}))
        self.assertTrue(result["success"])
        self.assertEqual("active", result["status"])

    def test_record_handler_uses_only_hook_captured_discord_text(self):
        self.assertTrue(hasattr(self.tools, "capture_trusted_discord_turn"))
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event()
        fake_discord = types.SimpleNamespace(Message=discord_type)
        fake_db = mock.Mock()
        prepared_discord_id = "123456789" + "012345678"
        prepared_cache_path = "/Users/" + "example/.hermes/cache/documents/file.txt"
        fake_db.get_messages.return_value = [{
            "id": 17,
            "role": "user",
            "content": (
                f"Discord user {prepared_discord_id} said:\n오늘 산책했어\n"
                f"{prepared_cache_path}"
            ),
            "api_content": "injected prepared document text",
        }]
        fake_state = types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db))
        fake_context = types.SimpleNamespace(get_session_env=self.session_context())
        with mock.patch.dict(sys.modules, {
            "discord": fake_discord,
            "hermes_state": fake_state,
            "gateway": types.ModuleType("gateway"),
            "gateway.session_context": fake_context,
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            payload = json.loads(self.tools.handle_life_os_record(
                {"operation": "answer", "attachment_paths": []},
            ))
        self.assertTrue(payload["success"])
        runtime.record.assert_called_once_with(
            "answer", message_text="오늘 산책했어",
            message_key=mock.ANY, attachment_paths=(),
            follow_up_question=None, target_date=None,
        )
        key = runtime.record.call_args.kwargs["message_key"]
        self.assertRegex(key, r"^hermes-discord:[0-9a-f]{64}$")
        self.assertNotIn(prepared_discord_id, runtime.record.call_args.kwargs["message_text"])
        self.assertNotIn(prepared_cache_path, runtime.record.call_args.kwargs["message_text"])

    def test_trusted_turn_rejects_batched_text_instead_of_committing_first_chunk(self):
        runtime = mock.Mock()
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        first = "첫 번째 청크"
        discord_type, event = self.discord_event(
            text=first,
            event_text=first + "\n두 번째 청크",
        )
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 20, "role": "user", "content": "prepared"}]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            "gateway": types.ModuleType("gateway"),
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            payload = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))

        self.assertFalse(payload["success"])
        runtime.record.assert_not_called()

    def test_trusted_turn_uses_caption_with_structurally_verified_document_injection(self):
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        caption = "회의 문서를 첨부했어"
        discord_type, event = self.discord_event(
            text=caption,
            event_text="[Content of notes.txt]:\nuntrusted document text\n\n" + caption,
            message_type="document",
            media_urls=("/tmp/cache/documents/notes.txt",),
            media_types=("text/plain",),
        )
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 21, "role": "user", "content": "prepared"}]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            "gateway": types.ModuleType("gateway"),
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            payload = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))

        self.assertTrue(payload["success"])
        self.assertEqual(caption, runtime.record.call_args.kwargs["message_text"])

    def test_trusted_turn_rejects_media_shape_without_structural_metadata(self):
        runtime = mock.Mock()
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event(
            text="첨부 설명",
            event_text="[Content of notes.txt]:\nuntrusted\n\n첨부 설명",
            message_type="document",
        )
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 24, "role": "user", "content": "prepared"}]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            "gateway": types.ModuleType("gateway"),
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            payload = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))

        self.assertFalse(payload["success"])
        runtime.record.assert_not_called()

    def test_trusted_turn_uses_deterministic_placeholder_for_attachment_only_event(self):
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event(
            text="",
            event_text="(The user sent a message with no text content)",
            message_type="photo",
            media_urls=("/tmp/cache/images/photo.jpg",),
            media_types=("image/jpeg",),
        )
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 22, "role": "user", "content": "prepared"}]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            "gateway": types.ModuleType("gateway"),
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            payload = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))

        self.assertTrue(payload["success"])
        self.assertEqual("첨부 파일", runtime.record.call_args.kwargs["message_text"])

    def test_trusted_turn_sensitive_content_fails_closed_but_ordinary_values_pass(self):
        sensitive = (
            "<@" + "123456789" + "012345678>",
            "123456789" + "012345678",
            "https://cdn." + "discordapp.com/attachments/file.txt",
            "/tmp/profile/.hermes/" + "cache/documents/file.txt",
            "/Users/" + "example/Documents/file.txt",
            "/home/" + "example/Documents/file.txt",
            "C:\\" + "Users\\example\\Documents\\file.txt",
            "sk-" + "a" * 32,
            "ghp_" + "b" * 36,
            "AKIA" + "C" * 16,
            "Bearer " + "d" * 32,
            "api_key=" + "e" * 32,
            "DISCORD_BOT_" + "TOKEN=" + "f" * 32,
            "-----BEGIN " + "PRIVATE KEY-----",
        )
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 23, "role": "user", "content": "prepared"}]
        base_modules = {
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            "gateway": types.ModuleType("gateway"),
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }
        for value in sensitive:
            with self.subTest(value=value):
                self.tools._TRUSTED_TURNS.clear()
                discord_type, event = self.discord_event(text="내 답 " + value)
                with mock.patch.dict(sys.modules, {
                    **base_modules,
                    "discord": types.SimpleNamespace(Message=discord_type),
                }):
                    self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
                    payload = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
                self.assertFalse(payload["success"])

        self.tools._TRUSTED_TURNS.clear()
        ordinary = "자연수 123456과 문서 https://example.com/report를 확인했어"
        discord_type, event = self.discord_event(text=ordinary)
        with mock.patch.dict(sys.modules, {
            **base_modules,
            "discord": types.SimpleNamespace(Message=discord_type),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            payload = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertTrue(payload["success"])
        self.assertEqual(1, runtime.record.call_count)
        self.assertEqual(ordinary, runtime.record.call_args.kwargs["message_text"])

    def test_record_handler_converts_paths_and_date(self):
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "completed"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event(text="기록")
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 18, "role": "user", "content": "prepared"}]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            "gateway": types.ModuleType("gateway"),
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            payload = json.loads(self.tools.handle_life_os_record(
                {
                    "operation": "free_record",
                    "date": "2026-08-06",
                    "follow_up_question": "더 있나요?",
                    "attachment_paths": ["/tmp/photo.png"],
                },
            ))
        self.assertTrue(payload["success"])
        runtime.record.assert_called_once_with(
            "free_record", message_text="기록",
            message_key=mock.ANY, attachment_paths=(Path("/tmp/photo.png"),),
            follow_up_question="더 있나요?", target_date=date(2026, 8, 6),
        )

    def test_record_fails_closed_for_absent_mismatched_stale_and_consumed_turns(self):
        self.assertTrue(hasattr(self.tools, "capture_trusted_discord_turn"))
        runtime = mock.Mock()
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event()
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 19, "role": "user", "content": "prepared"}]
        base_modules = {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            "gateway": types.ModuleType("gateway"),
        }

        with mock.patch.dict(sys.modules, {
            **base_modules,
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }):
            absent = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(absent["success"])

        with mock.patch.dict(sys.modules, {
            **base_modules,
            "gateway.session_context": types.SimpleNamespace(
                get_session_env=self.session_context(chat_id="other-chat"),
            ),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            mismatched = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(mismatched["success"])

        self.tools._TRUSTED_TURNS.clear()
        wrong_session_key = self.session_context()
        values = {
            name: wrong_session_key(name, "")
            for name in (
                "HERMES_SESSION_PLATFORM", "HERMES_SESSION_CHAT_ID",
                "HERMES_SESSION_USER_ID", "HERMES_SESSION_THREAD_ID",
                "HERMES_SESSION_PROFILE", "HERMES_SESSION_MESSAGE_ID",
                "HERMES_SESSION_ID", "HERMES_SESSION_KEY",
            )
        }
        values["HERMES_SESSION_KEY"] = "agent:other:discord:456:789"
        with mock.patch.dict(sys.modules, {
            **base_modules,
            "gateway.session_context": types.SimpleNamespace(
                get_session_env=lambda name, default="": values.get(name, default),
            ),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            cross_session = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(cross_session["success"])

        self.tools._TRUSTED_TURNS.clear()
        with mock.patch.dict(sys.modules, {
            **base_modules,
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }), mock.patch.object(self.tools.time, "monotonic", side_effect=(10.0, 10.0 + 301.0)):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            stale = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(stale["success"])

        self.tools._TRUSTED_TURNS.clear()
        runtime.record.return_value = {"status": "active"}
        with mock.patch.dict(sys.modules, {
            **base_modules,
            "gateway.session_context": types.SimpleNamespace(get_session_env=self.session_context()),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            first = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
            second = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertTrue(first["success"])
        self.assertFalse(second["success"])
        self.assertEqual(1, runtime.record.call_count)

    def test_trusted_turn_retries_after_transient_session_db_failure(self):
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event()
        fake_db = mock.Mock()
        fake_db.get_messages.side_effect = [
            RuntimeError("database busy"),
            [{"id": 26, "role": "user", "content": "prepared"}],
        ]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            first = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
            second = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(1, runtime.record.call_count)

    def test_trusted_turn_retries_runtime_failure_with_same_message_key(self):
        runtime = mock.Mock()
        runtime.record.side_effect = [self.tools.LifeOSError("transient"), {"status": "active"}]
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event()
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 27, "role": "user", "content": "prepared"}]
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            first = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
            second = json.loads(self.tools.handle_life_os_record({"operation": "answer"}))
        self.assertFalse(first["success"])
        self.assertTrue(second["success"])
        self.assertEqual(2, runtime.record.call_count)
        keys = [call.kwargs["message_key"] for call in runtime.record.call_args_list]
        self.assertEqual(keys[0], keys[1])

    def test_trusted_turn_reservation_allows_only_one_concurrent_runtime_call(self):
        entered = threading.Event()
        release = threading.Event()
        runtime = mock.Mock()

        def blocked_record(*_args, **_kwargs):
            entered.set()
            release.wait(2)
            return {"status": "active"}

        runtime.record.side_effect = blocked_record
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        discord_type, event = self.discord_event()
        fake_db = mock.Mock()
        fake_db.get_messages.return_value = [{"id": 28, "role": "user", "content": "prepared"}]
        results = []
        with mock.patch.dict(sys.modules, {
            "discord": types.SimpleNamespace(Message=discord_type),
            "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
        }):
            self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
            first = threading.Thread(
                target=lambda: results.append(json.loads(
                    self.tools.handle_life_os_record({"operation": "answer"}),
                )),
            )
            first.start()
            self.assertTrue(entered.wait(1))
            results.append(json.loads(self.tools.handle_life_os_record({"operation": "answer"})))
            release.set()
            first.join(2)
        self.assertFalse(first.is_alive())
        self.assertEqual(1, runtime.record.call_count)
        self.assertEqual([False, True], sorted(result["success"] for result in results))

    def test_trusted_turn_cache_never_exceeds_limit_when_all_entries_are_reserved(self):
        cache = self.tools._TrustedTurnCache()
        identities = [(str(index),) for index in range(self.tools._TRUSTED_TURN_LIMIT)]
        for identity in identities:
            cache.put(identity, "captured")
            cache.reserve(identity)
        cache.put(("overflow",), "must not be retained")
        self.assertEqual(self.tools._TRUSTED_TURN_LIMIT, len(cache._turns))
        with self.assertRaises(self.tools.CoreRuntimeError):
            cache.reserve(("overflow",))

    def test_trusted_turn_release_refreshes_ttl_for_retry(self):
        cache = self.tools._TrustedTurnCache()
        identity = ("retry",)
        cache.put(identity, "captured")
        cache.reserve(identity)
        _captured_at, text, reserved = cache._turns[identity]
        cache._turns[identity] = (
            time.monotonic() - self.tools._TRUSTED_TURN_TTL_SECONDS - 1,
            text,
            reserved,
        )
        cache.release(identity)
        self.assertEqual("captured", cache.reserve(identity))

    def test_trusted_turn_retries_after_note_commit_before_claim_commit(self):
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            vault = base / "vault"
            template = vault / "Life OS/0. PeriodicNotes/Templates/Daily.md"
            template.parent.mkdir(parents=True)
            template.write_text("## Daily Record\n%%Your Record%%\n", encoding="utf-8")
            runtime = self.tools.LifeOSRuntime(
                vault_root=vault,
                state_root=base / "state",
                timezone=ZoneInfo("Asia/Seoul"),
                cache_roots=(),
                max_attachment_bytes=1024,
            )
            setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
            discord_type, event = self.discord_event()
            fake_db = mock.Mock()
            fake_db.get_messages.return_value = [{"id": 29, "role": "user", "content": "prepared"}]
            original_commit = runtime._commit_global_claim
            original_record = runtime.record
            failed = False
            keys = []

            def fail_once(*args, **kwargs):
                nonlocal failed
                if not failed:
                    failed = True
                    raise self.tools.LifeOSError("post-note claim failure")
                return original_commit(*args, **kwargs)

            def track_record(*args, **kwargs):
                keys.append(kwargs["message_key"])
                return original_record(*args, **kwargs)

            with mock.patch.dict(sys.modules, {
                "discord": types.SimpleNamespace(Message=discord_type),
                "hermes_state": types.SimpleNamespace(SessionDB=mock.Mock(return_value=fake_db)),
            }), mock.patch.object(runtime, "_commit_global_claim", side_effect=fail_once), mock.patch.object(
                runtime, "record", side_effect=track_record,
            ):
                self.tools.capture_trusted_discord_turn(event=event, gateway=self.gateway())
                first = json.loads(self.tools.handle_life_os_record({"operation": "free_record"}))
                second = json.loads(self.tools.handle_life_os_record({"operation": "free_record"}))
            note = Path(second["path"]).read_text(encoding="utf-8")
        self.assertFalse(first["success"])
        self.assertTrue(second["success"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(keys[0], keys[1])
        self.assertEqual(1, note.count("오늘 산책했어"))

    def test_life_os_runtime_singleton_is_separate_and_thread_safe(self):
        core_runtime = object()
        setattr(self.tools, "_RUNTIME", core_runtime)
        setattr(self.tools, "_LIFE_OS_RUNTIME", None)
        created = []

        def create_runtime():
            time.sleep(0.03)
            value = object()
            created.append(value)
            return value

        results = []
        with mock.patch.object(
            self.tools.LifeOSRuntime, "from_environment", side_effect=create_runtime,
        ):
            threads = [
                threading.Thread(target=lambda: results.append(self.tools._life_os_runtime()))
                for _ in range(8)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(1, len(created))
        self.assertEqual(1, len({id(value) for value in results}))
        self.assertIs(core_runtime, self.tools._RUNTIME)


if __name__ == "__main__":
    unittest.main()
