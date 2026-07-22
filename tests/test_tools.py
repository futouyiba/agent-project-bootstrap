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

            second = run(command, REPOSITORY)
            self.assertEqual(second.returncode, 0, second.stderr)
            agents = (codex_root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertEqual(agents.count("<!-- agent-project-bootstrap:start -->"), 1)


if __name__ == "__main__":
    unittest.main()
