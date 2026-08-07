import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "donggu-obsidian" / "skills" / "life-os" / "SKILL.md"
CLI = SKILL.parent / "scripts" / "life-os.py"
ROOT_README = ROOT / "README.md"
PLUGIN_README = ROOT / "donggu-obsidian" / "README.md"
DESIGN = ROOT / "docs/superpowers/specs/2026-08-07-hermes-life-os-discord-design.md"
PLAN = ROOT / "docs/superpowers/plans/2026-08-07-hermes-life-os-discord.md"


class LifeOSSkillContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.vault = self.base / "vault"
        template = self.vault / "Life OS/0. PeriodicNotes/Templates/Daily.md"
        template.parent.mkdir(parents=True)
        template.write_text(
            "## Project List\n<% LifeOS.Project.snapshot() %>\n\n"
            "## Daily Record\n%%Your Record%%\n",
            encoding="utf-8",
        )
        self.env = {**os.environ, "HOME": str(self.base)}

    def run_cli(self, *args, input_text=""):
        return subprocess.run(
            [sys.executable, str(CLI), "--vault-root", str(self.vault), *args],
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            cwd=self.base,
            env=self.env,
        )

    def test_skill_declares_questions_routes_and_native_tools(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("name: life-os", text)
        for question in (
            "오늘 어떤 일이 있었나?", "감정과 에너지는 어떤가?",
            "진행한 일과 막힌 일은?", "생각·배움·결정은?",
            "내일 가장 중요한 한 가지는?",
        ):
            self.assertEqual(1, text.count(question))
        for tool in (
            "donggu_life_os_status",
            "donggu_life_os_start_daily",
            "donggu_life_os_record",
        ):
            self.assertIn(tool, text)
        self.assertIn("Hermes cache path", text)
        self.assertIn("최대 2개", text)

    def test_skill_is_imperative_and_encodes_exact_hermes_recipe(self):
        text = SKILL.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line]
        self.assertEqual(["name", "description"], keys)
        self.assertRegex(frontmatter, r"(?m)^description: Use when ")
        routing = (
            "## Routing\n\n"
            "- “오늘 정리하자” or no explicit period in the dedicated channel → Daily.\n"
            "- “일단 기록해줘” → Capture.\n"
            "- “어제 이어서” → yesterday's Daily."
        )
        hermes = (
            "## Hermes path\n\n"
            "1. Call `donggu_life_os_status` before interpreting a normal channel message.\n"
            "2. Start only on an explicit start command or the scheduled start prompt.\n"
            "3. During an active check-in, call `donggu_life_os_record` once for the trusted latest turn.\n"
            "4. Return only the tool's next question or completion summary.\n"
            "5. Never use generic filesystem tools as a fallback when a native tool fails."
        )
        self.assertIn(routing, text)
        self.assertIn(hermes, text)
        for phrase in (
            "건너뛰기", "그만", "이어서 하자", "free Daily record",
            "Life OS/0. PeriodicNotes/", "Life OS/-1. Capture/",
            "Life OS/Attachments/", "Claude Code", "Codex",
        ):
            self.assertIn(phrase, text)

    def test_public_life_os_contract_advertises_only_daily_and_capture_routes(self):
        sources = (
            SKILL,
            ROOT / "docs/superpowers/specs/2026-08-07-hermes-life-os-discord-design.md",
            ROOT / "docs/superpowers/plans/2026-08-07-hermes-life-os-discord.md",
        )
        forbidden = ("Weekly", "Monthly", "Quarterly", "Yearly", "이번 주/달/분기/연도")
        for source in sources:
            text = source.read_text(encoding="utf-8")
            for phrase in forbidden:
                with self.subTest(source=source.name, phrase=phrase):
                    self.assertNotIn(phrase, text)
        skill = SKILL.read_text(encoding="utf-8")
        self.assertIn("Daily and Capture only", skill)
        self.assertIn("첨부 파일", skill)

    def test_skill_declares_exact_record_calls_and_trusted_handler_boundary(self):
        text = SKILL.read_text(encoding="utf-8")
        for operation in ("answer", "skip", "pause", "resume", "capture", "free_record"):
            with self.subTest(operation=operation):
                self.assertIn(
                    f'`donggu_life_os_record(operation="{operation}")`',
                    text,
                )
        for contract in (
            "Every `donggu_life_os_record` call requires `operation`",
            "Add `follow_up_question` only to an `answer` call",
            "Add `attachment_paths` only when the latest turn includes attachments",
            "Add `date` only for an explicit target date",
            "Never pass `control`, `text`, `message_text`, `message_key`, or `session_id`",
            "uses the trusted Discord-authored turn captured before gateway preparation",
            "uses `SessionDB` only for the persisted user row ID",
            "constructs the trusted key from the Hermes session, row, platform, and source identities",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, text)

    def test_skill_and_design_declare_origin_and_resume_boundaries(self):
        skill = SKILL.read_text(encoding="utf-8")
        design = DESIGN.read_text(encoding="utf-8")
        for phrase in (
            "exact configured `life-os` Discord channel binding",
            "Cron may call only `donggu_life_os_start_daily`",
            "status and record are forbidden from cron",
            "reserved until the runtime call succeeds",
            "explicit start resumes a paused Daily",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, skill + "\n" + design)

    def test_discord_bootstrap_uses_requests_hermes_user_agent_and_get_readback(self):
        plan = PLAN.read_text(encoding="utf-8")
        for phrase in (
            "import requests",
            '"User-Agent": "Hermes-Agent (https://github.com/NousResearch/hermes-agent)"',
            "requests.request(",
            'readback = request("GET", f"/channels/{channel[\'id\']}")',
            'readback.get("guild_id") != guild["id"]',
            'readback.get("type") != 0',
            'readback.get("parent_id") != parent_id',
            'readback.get("name") != "life-os"',
            "successful GET proves the bot can view the channel",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, plan)

    def test_cron_reconciliation_and_smoke_commands_use_one_exact_job_id(self):
        plan = PLAN.read_text(encoding="utf-8")
        for phrase in (
            'LIFE_OS_CRON_LIST="$(hermes cron list --all)"',
            'LIFE_OS_CRON_CREATE="$(hermes cron create',
            'LIFE_OS_CRON_JOB_ID',
            'expected exactly one cron job ID for the exact job name',
            'hermes cron run "$LIFE_OS_CRON_JOB_ID"',
            'hermes cron runs "$LIFE_OS_CRON_JOB_ID" --limit 5',
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, plan)

    def test_cli_status_start_and_record_use_shared_runtime(self):
        status = self.run_cli("status", "--date", "2026-08-07")
        self.assertEqual(0, status.returncode, status.stderr)
        self.assertEqual("not_started", json.loads(status.stdout)["status"])

        start = self.run_cli("start", "--date", "2026-08-07")
        self.assertEqual(0, start.returncode, start.stderr)
        self.assertEqual("오늘 어떤 일이 있었나?", json.loads(start.stdout)["question"])

        record = self.run_cli(
            "record", "answer", "--date", "2026-08-07",
            "--message-key", "manual:test", input_text="산책을 했다",
        )
        self.assertEqual(0, record.returncode, record.stderr)
        self.assertEqual("감정과 에너지는 어떤가?", json.loads(record.stdout)["question"])
        note = self.vault / "Life OS/0. PeriodicNotes/2026/Daily/08/2026-08-07.md"
        self.assertIn("산책을 했다", note.read_text(encoding="utf-8"))

    def test_cli_explicit_start_resumes_paused_daily_without_resetting_progress(self):
        day = "2026-08-07"
        self.assertEqual(0, self.run_cli("start", "--date", day).returncode)
        answer = self.run_cli(
            "record", "answer", "--date", day,
            "--message-key", "manual:answer", input_text="첫 답",
        )
        self.assertEqual(0, answer.returncode, answer.stderr)
        pause = self.run_cli(
            "record", "pause", "--date", day,
            "--message-key", "manual:pause", input_text="그만",
        )
        self.assertEqual(0, pause.returncode, pause.stderr)

        resumed = self.run_cli("start", "--date", day)
        self.assertEqual(0, resumed.returncode, resumed.stderr)
        payload = json.loads(resumed.stdout)
        self.assertEqual("active", payload["status"])
        self.assertEqual(2, payload["next_question"])
        note = self.vault / "Life OS/0. PeriodicNotes/2026/Daily/08/2026-08-07.md"
        text = note.read_text(encoding="utf-8")
        self.assertEqual(1, text.count("첫 답"))

    def test_cli_start_rejects_removed_resume_option(self):
        proc = self.run_cli("start", "--resume", "--date", "2026-08-07")
        self.assertEqual(2, proc.returncode)
        self.assertIn("unrecognized arguments: --resume", proc.stderr)

    def test_cli_reports_runtime_errors_on_stderr_with_exit_code_2(self):
        proc = subprocess.run(
            [sys.executable, str(CLI), "--vault-root", str(self.base / "missing"), "status"],
            text=True,
            capture_output=True,
            check=False,
            cwd=self.base,
            env=self.env,
        )
        self.assertEqual(2, proc.returncode)
        self.assertEqual("", proc.stdout)
        self.assertIn("Vault root is unavailable", proc.stderr)

    def test_public_docs_cover_installation_configuration_and_counts(self):
        root = ROOT_README.read_text(encoding="utf-8")
        plugin = PLUGIN_README.read_text(encoding="utf-8")
        self.assertIn("skills-17-green", root)
        self.assertIn("skills-6-green", plugin)
        for text in (root, plugin):
            self.assertIn("life-os", text)
            self.assertIn("/donggu-obsidian:life-os", text)
        for token in (
            "DONGGU_LIFE_OS_VAULT_ROOT", "DONGGU_LIFE_OS_STATE_ROOT",
            "DONGGU_LIFE_OS_TIMEZONE", "hermes plugins install",
            "channel_skill_bindings", "<life-os-channel-id>", "0 22 * * *",
            "Asia/Seoul", ".codex/skills/life-os", "Life OS/Attachments/",
            "free_response_channels", "channel_prompts",
            "allowed_channels", "hermes cron create", "hermes cron edit",
            "hermes cron list --all", 'hermes cron run "$LIFE_OS_CRON_JOB_ID"',
            'hermes cron runs "$LIFE_OS_CRON_JOB_ID" --limit 5',
            '--deliver "discord:${LIFE_OS_CHANNEL_ID}"', "--skill life-os",
            '--workdir \"$LIFE_OS_VAULT_ROOT\"',
        ):
            self.assertIn(token, plugin)
        self.assertNotIn("require_mention: false", plugin)
        self.assertIn("기존 global `require_mention` 값은 보존", plugin)


if __name__ == "__main__":
    unittest.main()
