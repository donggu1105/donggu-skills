#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

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
        self.assertEqual("2.5.0", claude["version"])
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
        self.assertIn("SNS_WEBHOOK_TOKEN", dispatch["requires_env"])
        self.assertIn("SUPABASE_SERVICE_KEY", dispatch["requires_env"])

    def test_obsidian_claude_and_hermes_manifests_share_identity_and_version(self):
        package = ROOT / "donggu-obsidian"
        claude = json.loads((package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        hermes = package / "plugin.yaml"
        self.assertEqual("donggu-obsidian", claude["name"])
        self.assertEqual(claude["name"], manifest_scalar(hermes, "name"))
        self.assertEqual("1.6.0", claude["version"])
        self.assertEqual(claude["version"], manifest_scalar(hermes, "version"))

    def test_obsidian_registers_exact_native_tool_surface(self):
        package = load_package(ROOT / "donggu-obsidian", "donggu_obsidian_plugin_test")
        ctx = FakeContext()
        package.register(ctx)
        self.assertEqual(
            ["donggu_core_plan", "donggu_core_apply", "donggu_core_recovery_status"],
            [item["name"] for item in ctx.tools],
        )
        self.assertTrue(all(item["toolset"] == "donggu_obsidian" for item in ctx.tools))


if __name__ == "__main__":
    unittest.main()
