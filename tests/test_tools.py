from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
AUDIT = REPOSITORY / "skill" / "scripts" / "audit_project.py"
SNAPSHOT = REPOSITORY / "skill" / "scripts" / "snapshot_github.py"


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


class AuditTests(unittest.TestCase):
    def test_non_repository_is_reported_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run([sys.executable, str(AUDIT), str(root)], root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["reason"], "not_git_repository")
            self.assertEqual(list(root.iterdir()), [])

    def test_stack_and_coordination_detection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            (root / "package.json").write_text('{"scripts":{"test":"node --test"}}\n', encoding="utf-8")
            (root / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
            (root / "AGENTS.md").write_text("# Test\n", encoding="utf-8")
            (root / ".gitignore").write_text(".env.local\n", encoding="utf-8")
            (root / ".env.local").write_text("DO_NOT_READ=1\n", encoding="utf-8")
            ignored = run(["git", "check-ignore", "-v", ".env.local"], root)
            self.assertEqual(ignored.returncode, 0, ignored.stderr)
            workflow = root / ".github" / "workflows"
            workflow.mkdir(parents=True)
            (workflow / "ci.yml").write_text("name: CI\n", encoding="utf-8")

            result = run([sys.executable, str(AUDIT), str(root)], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["detected_stacks"], ["node"])
            self.assertEqual(report["node_package_manager"], "npm")
            self.assertTrue(report["coordination"]["agents_md"])
            self.assertEqual(report["coordination"]["workflows"], [".github/workflows/ci.yml"])
            self.assertEqual(report["ignored_local_files_for_review"], [".env.local"])
            self.assertNotIn("DO_NOT_READ", result.stdout)


class SnapshotTests(unittest.TestCase):
    def test_status_reads_existing_cache_without_github_network(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            cache = root / ".codex" / "cache" / "github-snapshot.json"
            cache.parent.mkdir(parents=True)
            cache.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "repository": "example/project",
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "issues": [{"number": 1}],
                        "pull_requests": [{"number": 2}],
                    }
                ),
                encoding="utf-8",
            )

            result = run([sys.executable, str(SNAPSHOT), "status", str(root)], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads(result.stdout)
            self.assertTrue(status["exists"])
            self.assertEqual(status["repository"], "example/project")
            self.assertEqual(status["issue_count"], 1)
            self.assertEqual(status["pull_request_count"], 1)


@unittest.skipIf(os.name == "nt", "POSIX installer test")
class PosixInstallerTests(unittest.TestCase):
    def test_local_install_and_global_rule_are_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_root = Path(directory) / "codex"
            prompts_root = codex_root / "prompts"
            prompts_root.mkdir(parents=True)
            (prompts_root / "integrate.md").write_text("user-owned prompt\n", encoding="utf-8")
            command = [
                "sh",
                str(REPOSITORY / "install.sh"),
                "--source",
                str(REPOSITORY),
                "--codex-home",
                str(codex_root),
                "--with-global-rule",
            ]
            first = run(command, REPOSITORY)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = codex_root / "skills" / "agent-project-bootstrap"
            self.assertTrue((destination / "SKILL.md").exists())
            self.assertTrue((destination / "scripts" / "snapshot_github.py").exists())
            self.assertTrue((destination / "assets" / "codex-managed-supervisor.md").exists())
            integrate_prompt = codex_root / "prompts" / "integrate.md"
            self.assertTrue(integrate_prompt.exists())
            self.assertIn("Use $$agent-project-bootstrap", integrate_prompt.read_text(encoding="utf-8"))
            prompt_backups = list((codex_root / "prompts").glob("integrate.md.backup.*"))
            self.assertEqual(len(prompt_backups), 1)
            self.assertEqual(prompt_backups[0].read_text(encoding="utf-8"), "user-owned prompt\n")

            agents_file = codex_root / "AGENTS.md"
            old_rule = agents_file.read_text(encoding="utf-8").replace(
                "Accept natural-language task descriptions and never require the user to know an Issue number.",
                "OUTDATED RULE",
            )
            agents_file.write_text(old_rule, encoding="utf-8")

            second = run(command, REPOSITORY)
            self.assertEqual(second.returncode, 0, second.stderr)
            agents = agents_file.read_text(encoding="utf-8")
            self.assertEqual(agents.count("<!-- agent-project-bootstrap:start -->"), 1)
            self.assertNotIn("OUTDATED RULE", agents)
            self.assertIn("never require the user to know an Issue number", agents)
            self.assertIn("合并收尾", agents)
            self.assertIn("托管这个项目", agents)
            self.assertIn("one durable supervisor", agents)
            self.assertEqual(len(list((codex_root / "prompts").glob("integrate.md.backup.*"))), 1)

    def test_partial_global_rule_fails_without_losing_user_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_root = Path(directory) / "codex"
            codex_root.mkdir(parents=True)
            agents_file = codex_root / "AGENTS.md"
            original = "before\n<!-- agent-project-bootstrap:start -->\nstale rule\nafter\n"
            agents_file.write_text(original, encoding="utf-8")

            result = run(
                [
                    "sh",
                    str(REPOSITORY / "install.sh"),
                    "--source",
                    str(REPOSITORY),
                    "--codex-home",
                    str(codex_root),
                    "--with-global-rule",
                ],
                REPOSITORY,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("markers are incomplete or duplicated", result.stderr)
            self.assertEqual(agents_file.read_text(encoding="utf-8"), original)

    def test_out_of_order_global_rule_fails_without_losing_user_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_root = Path(directory) / "codex"
            codex_root.mkdir(parents=True)
            agents_file = codex_root / "AGENTS.md"
            original = (
                "before\n<!-- agent-project-bootstrap:end -->\nstale rule\n"
                "<!-- agent-project-bootstrap:start -->\nafter\n"
            )
            agents_file.write_text(original, encoding="utf-8")

            result = run(
                [
                    "sh",
                    str(REPOSITORY / "install.sh"),
                    "--source",
                    str(REPOSITORY),
                    "--codex-home",
                    str(codex_root),
                    "--with-global-rule",
                ],
                REPOSITORY,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("markers are out of order", result.stderr)
            self.assertEqual(agents_file.read_text(encoding="utf-8"), original)

    def test_same_line_duplicate_markers_fail_without_losing_user_content(self) -> None:
        marker_pairs = (
            (
                "<!-- agent-project-bootstrap:start -->" * 2,
                "<!-- agent-project-bootstrap:end -->",
            ),
            (
                "<!-- agent-project-bootstrap:start -->",
                "<!-- agent-project-bootstrap:end -->" * 2,
            ),
        )
        for start_markers, end_markers in marker_pairs:
            with self.subTest(start_markers=start_markers, end_markers=end_markers):
                with tempfile.TemporaryDirectory() as directory:
                    codex_root = Path(directory) / "codex"
                    codex_root.mkdir(parents=True)
                    agents_file = codex_root / "AGENTS.md"
                    original = f"before\n{start_markers}\nstale rule\n{end_markers}\nafter\n"
                    agents_file.write_text(original, encoding="utf-8")

                    result = run(
                        [
                            "sh",
                            str(REPOSITORY / "install.sh"),
                            "--source",
                            str(REPOSITORY),
                            "--codex-home",
                            str(codex_root),
                            "--with-global-rule",
                        ],
                        REPOSITORY,
                    )

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("markers are incomplete or duplicated", result.stderr)
                    self.assertEqual(agents_file.read_text(encoding="utf-8"), original)


class SkillContractTests(unittest.TestCase):
    def test_one_skill_contains_bootstrap_and_daily_modes(self) -> None:
        skill = (REPOSITORY / "skill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Bootstrap mode", skill)
        self.assertIn("## Daily-flow mode", skill)
        self.assertIn("bootstrap mode first", skill)
        self.assertIn("Preserve the pending task description", skill)
        self.assertIn("Never require the user to supply an Issue number", skill)
        for shortcut in ("记一下", "收需求", "开始做", "收尾", "合并收尾", "托管这个项目"):
            self.assertIn(shortcut, skill)

        daily_flow = (REPOSITORY / "skill" / "references" / "daily-project-flow.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Integrate approved pull requests", daily_flow)
        self.assertIn("Merge one PR, refresh GitHub state", daily_flow)
        self.assertIn("does not include deployment", daily_flow)

    def test_managed_mode_has_bounded_supervisor_contract(self) -> None:
        skill = (REPOSITORY / "skill" / "SKILL.md").read_text(encoding="utf-8")
        managed = (REPOSITORY / "skill" / "references" / "managed-autopilot.md").read_text(
            encoding="utf-8"
        )
        prompt = (REPOSITORY / "skill" / "assets" / "codex-managed-supervisor.md").read_text(
            encoding="utf-8"
        )
        marker = (REPOSITORY / ".codex" / "agent-project-bootstrap.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("## Managed mode", skill)
        self.assertIn("Do not depend on the user copying messages", skill)
        self.assertIn("retry limit", managed)
        self.assertIn("Default human gates", managed)
        self.assertIn("qualified_auto_merge", managed)
        self.assertIn("Scheduled heartbeats are not GitHub webhooks", managed)
        self.assertIn("end this heartbeat quietly", prompt)
        self.assertIn("Never deploy or publish", prompt)
        self.assertIn("version: 4", marker)
        self.assertIn("managed_mode:", marker)
        self.assertIn("level: off", marker)
        self.assertIn("goal_scope: null", marker)
        self.assertIn("retry_limit: 3", marker)
        self.assertIn("merge_policy: per_turn", marker)

    def test_repository_template_contains_authorization_boundary(self) -> None:
        template = (REPOSITORY / "templates" / "AGENTS.project.md").read_text(encoding="utf-8")
        self.assertIn("## Standing authorization", template)
        self.assertIn("Project URL: `<project-url-or-pending>`", template)
        self.assertIn("Validation commands", template)
        self.assertIn("Ask before", template)
        self.assertIn("merging", template)
        self.assertIn("## Managed supervisor", template)
        self.assertIn("Heartbeat: `<schedule-or-pending>`", template)
        self.assertIn("Retry limit: `<integer-default-3>`", template)
        self.assertIn("Merge policy: `<per_turn|qualified_auto_merge|manual>`", template)
        self.assertIn("Deployment and publishing", template)


if __name__ == "__main__":
    unittest.main()
