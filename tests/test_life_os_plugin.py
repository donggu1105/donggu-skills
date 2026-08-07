#!/usr/bin/env python3
from datetime import date
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
import unittest
from unittest import mock


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

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


class LifeOSPluginTests(unittest.TestCase):
    def setUp(self):
        self.module_name = f"life_os_plugin_test_{self._testMethodName}"
        self.package = load_package(ROOT / "donggu-obsidian", self.module_name)
        self.tools = importlib.import_module(self.module_name + ".tools")

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
        runtime.start_daily.assert_called_once_with(None)

    def test_record_handler_uses_latest_session_db_text(self):
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "active"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        with mock.patch.object(
            self.tools, "_latest_trusted_user_message", return_value=(17, "오늘 산책했어"),
        ):
            payload = json.loads(self.tools.handle_life_os_record(
                {"operation": "answer", "attachment_paths": []},
                session_id="discord-session",
            ))
        self.assertTrue(payload["success"])
        runtime.record.assert_called_once_with(
            "answer", message_text="오늘 산책했어",
            message_key="discord-session:17", attachment_paths=(),
            follow_up_question=None, target_date=None,
        )

    def test_record_handler_converts_paths_and_date(self):
        runtime = mock.Mock()
        runtime.record.return_value = {"status": "completed"}
        setattr(self.tools, "_LIFE_OS_RUNTIME", runtime)
        with mock.patch.object(
            self.tools, "_latest_trusted_user_message", return_value=(18, "기록"),
        ):
            payload = json.loads(self.tools.handle_life_os_record(
                {
                    "operation": "free_record",
                    "date": "2026-08-06",
                    "follow_up_question": "더 있나요?",
                    "attachment_paths": ["/tmp/photo.png"],
                },
                session_id="discord-session",
            ))
        self.assertTrue(payload["success"])
        runtime.record.assert_called_once_with(
            "free_record", message_text="기록",
            message_key="discord-session:18", attachment_paths=(Path("/tmp/photo.png"),),
            follow_up_question="더 있나요?", target_date=date(2026, 8, 6),
        )

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
