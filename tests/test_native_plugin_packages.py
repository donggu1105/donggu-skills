#!/usr/bin/env python3
import importlib.util
import importlib
import json
from pathlib import Path
import re
import sys
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

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)


class NativePluginPackageTests(unittest.TestCase):
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
        self.assertEqual("2.5.1", claude["version"])
        self.assertEqual(claude["version"], manifest_scalar(hermes, "version"))

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

            def approve(self, receipt_id, *, approval_text, session_id, turn_id, user_message_id):
                self.approval_text = approval_text
                self.user_message_id = user_message_id
                return {"status": "approved", "receipt_id": receipt_id}

        fake = FakeRuntime()
        setattr(tools, "_RUNTIME", fake)
        with mock.patch.object(tools, "_latest_trusted_user_message", return_value=(2, "[강동현] 승인")):
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
        self.assertEqual("1.6.1", claude["version"])
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

    def test_obsidian_registers_exact_native_tool_surface(self):
        package = load_package(ROOT / "donggu-obsidian", "donggu_obsidian_plugin_test")
        ctx = FakeContext()
        package.register(ctx)
        self.assertEqual(
            ["donggu_core_plan", "donggu_core_apply", "donggu_core_recovery_status"],
            [item["name"] for item in ctx.tools],
        )
        apply_tool = next(item for item in ctx.tools if item["name"] == "donggu_core_apply")
        self.assertEqual(["receipt_id"], apply_tool["schema"]["parameters"]["required"])
        self.assertTrue(all(item["toolset"] == "donggu_obsidian" for item in ctx.tools))


if __name__ == "__main__":
    unittest.main()
