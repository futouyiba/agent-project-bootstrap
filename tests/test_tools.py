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
AGENTIC = REPOSITORY / "skill" / "scripts" / "configure_agentic_workflows.py"


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


class AgenticWorkflowConfiguratorTests(unittest.TestCase):
    def test_plan_is_read_only_and_defaults_to_staged_codex(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            result = run([sys.executable, str(AGENTIC), str(root)], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["engine"], "codex")
            self.assertEqual(report["rollout"], "staged")
            self.assertEqual(report["required_secret"], "OPENAI_API_KEY")
            self.assertTrue(all(item["action"] == "create" for item in report["files"]))
            self.assertFalse((root / ".github").exists())

    def test_apply_renders_four_workflows_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            command = [
                sys.executable,
                str(AGENTIC),
                str(root),
                "--engine",
                "codex",
                "--apply",
            ]
            first = run(command, root)
            self.assertEqual(first.returncode, 0, first.stderr)
            workflows = sorted((root / ".github" / "workflows").glob("agent-*.md"))
            self.assertEqual(len(workflows), 4)
            for workflow in workflows:
                content = workflow.read_text(encoding="utf-8")
                self.assertIn("engine: codex", content)
                self.assertIn("staged: true", content)
                self.assertNotIn("__ENGINE__", content)
                self.assertNotIn("__STAGED__", content)
                self.assertNotIn("__CI_BRANCH_PATTERN__", content)
                self.assertNotIn("__CI_WORKFLOW__", content)

            second = run(command, root)
            self.assertEqual(second.returncode, 0, second.stderr)
            report = json.loads(second.stdout)
            self.assertTrue(all(item["action"] == "unchanged" for item in report["files"]))

    def test_first_install_cannot_enable_live_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)

            result = run([sys.executable, str(AGENTIC), str(root), "--live", "--apply"], root)

            self.assertEqual(result.returncode, 5)
            report = json.loads(result.stdout)
            self.assertEqual(len(report["blocked"]), 4)
            self.assertTrue(
                all(item["action"] == "requires_staged_install" for item in report["files"])
            )
            self.assertFalse((root / ".github").exists())

    def test_exact_staged_install_can_be_promoted_to_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            staged = run([sys.executable, str(AGENTIC), str(root), "--apply"], root)
            self.assertEqual(staged.returncode, 0, staged.stderr)

            preview = run([sys.executable, str(AGENTIC), str(root), "--live"], root)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertTrue(
                all(
                    item["action"] == "promote_to_live"
                    for item in json.loads(preview.stdout)["files"]
                )
            )

            promoted = run(
                [sys.executable, str(AGENTIC), str(root), "--live", "--apply"], root
            )
            self.assertEqual(promoted.returncode, 0, promoted.stderr)
            for workflow in (root / ".github" / "workflows").glob("agent-*.md"):
                self.assertIn("staged: false", workflow.read_text(encoding="utf-8"))

    def test_modified_staged_install_cannot_be_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            self.assertEqual(
                run([sys.executable, str(AGENTIC), str(root), "--apply"], root).returncode,
                0,
            )
            workflows = root / ".github" / "workflows"
            modified = workflows / "agent-review.md"
            modified.write_text(
                modified.read_text(encoding="utf-8") + "\nuser change\n", encoding="utf-8"
            )

            result = run(
                [sys.executable, str(AGENTIC), str(root), "--live", "--apply"], root
            )

            self.assertEqual(result.returncode, 3)
            self.assertIn("user change", modified.read_text(encoding="utf-8"))
            for workflow in workflows.glob("agent-*.md"):
                self.assertIn("staged: true", workflow.read_text(encoding="utf-8"))

    def test_symlinked_workflow_directory_is_rejected_without_external_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            container = Path(directory)
            root = container / "repository"
            outside = container / "outside"
            root.mkdir()
            outside.mkdir()
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            github = root / ".github"
            github.mkdir()
            try:
                os.symlink(outside, github / "workflows", target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symbolic links unavailable: {error}")

            result = run([sys.executable, str(AGENTIC), str(root), "--apply"], root)

            self.assertEqual(result.returncode, 6)
            self.assertEqual(json.loads(result.stdout)["reason"], "unsafe_destination")
            self.assertEqual(list(outside.iterdir()), [])

    def test_conflict_refuses_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            conflict = workflows / "agent-review.md"
            conflict.write_text("user-owned\n", encoding="utf-8")

            result = run([sys.executable, str(AGENTIC), str(root), "--apply"], root)
            self.assertEqual(result.returncode, 3)
            self.assertEqual(conflict.read_text(encoding="utf-8"), "user-owned\n")
            self.assertFalse((workflows / "agent-supervisor.md").exists())


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
            self.assertTrue((destination / "scripts" / "configure_agentic_workflows.py").exists())
            self.assertTrue(
                (destination / "assets" / "github-agentic-workflows" / "agent-supervisor.md").exists()
            )
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
            self.assertIn("and `托管` as shortcuts", agents)
            self.assertIn("Bare `托管` means the current repository", agents)
            self.assertIn("one durable supervisor", agents)
            self.assertIn("GitHub Agentic Workflows profile", agents)
            self.assertIn("staged on first installation", agents)
            self.assertIn("`Ready for review` is a pull-request stage only", agents)
            self.assertIn("without waiting for review or approval", agents)
            self.assertIn("Do not create an approver-only Agent", agents)
            self.assertIn("Never send work back to the implementer solely", agents)
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

    def test_markers_sharing_lines_with_user_text_fail_without_losing_content(self) -> None:
        start = "<!-- agent-project-bootstrap:start -->"
        end = "<!-- agent-project-bootstrap:end -->"
        originals = (
            f"before {start}\nold rule\n{end}\nafter\n",
            f"before\n{start}\nold rule\n{end} after\n",
            f"before {start}\nold rule\n{end} after\n",
        )
        for original in originals:
            with self.subTest(original=original):
                with tempfile.TemporaryDirectory() as directory:
                    codex_root = Path(directory) / "codex"
                    codex_root.mkdir(parents=True)
                    agents_file = codex_root / "AGENTS.md"
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
                    self.assertIn("markers must be on their own lines", result.stderr)
                    self.assertEqual(agents_file.read_text(encoding="utf-8"), original)


class SkillContractTests(unittest.TestCase):
    def test_one_skill_contains_bootstrap_and_daily_modes(self) -> None:
        skill = (REPOSITORY / "skill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("## Bootstrap mode", skill)
        self.assertIn("## Daily-flow mode", skill)
        self.assertIn("bootstrap mode first", skill)
        self.assertIn("Preserve the pending task description", skill)
        self.assertIn("Never require the user to supply an Issue number", skill)
        for shortcut in ("记一下", "收需求", "开始做", "收尾", "合并收尾", "托管"):
            self.assertIn(shortcut, skill)

        daily_flow = (REPOSITORY / "skill" / "references" / "daily-project-flow.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Integrate merge-ready pull requests", daily_flow)
        self.assertIn("Merge one PR, refresh GitHub state", daily_flow)
        self.assertIn("does not include deployment", daily_flow)
        self.assertIn("`Ready for review` is a PR stage", daily_flow)
        self.assertIn("without handing the task back to the implementer", daily_flow)

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
        self.assertIn("With no suffix, use the current repository", skill)
        self.assertIn("Treat `托管这个项目` and natural equivalents identically", skill)
        self.assertIn("Do not depend on the user copying messages", skill)
        self.assertIn("retry limit", managed)
        self.assertIn("Default human gates", managed)
        self.assertIn("qualified_auto_merge", managed)
        self.assertIn("Scheduled heartbeats are not GitHub webhooks", managed)
        self.assertIn("end this heartbeat quietly", prompt)
        self.assertIn("Never deploy or publish", prompt)
        self.assertIn("version: 5", marker)
        self.assertIn("managed_mode:", marker)

        marker_lines = marker.splitlines()
        managed_start = marker_lines.index("managed_mode:") + 1
        managed_config: dict[str, str] = {}
        for line in marker_lines[managed_start:]:
            if not line.startswith("  "):
                break
            key, value = line.strip().split(":", 1)
            managed_config[key] = value.strip()

        required_managed_fields = {
            "enabled",
            "level",
            "goal_scope",
            "supervisor",
            "heartbeat",
            "local_client_required",
            "retry_limit",
            "automatic_review",
            "merge_policy",
            "low_risk_merge_criteria",
            "high_risk_paths_or_labels",
            "human_gates",
            "deployment_and_publishing",
        }
        self.assertLessEqual(required_managed_fields, set(managed_config))
        self.assertIn(managed_config["enabled"], {"true", "false"})
        self.assertTrue(managed_config["retry_limit"].isdigit())
        self.assertGreater(int(managed_config["retry_limit"]), 0)
        self.assertIn(
            managed_config["merge_policy"],
            {"per_turn", "qualified_auto_merge", "manual"},
        )
        self.assertEqual(managed_config["deployment_and_publishing"], "never")

        if managed_config["enabled"] == "false":
            self.assertEqual(managed_config["level"], "off")
            self.assertEqual(managed_config["goal_scope"], "null")
            self.assertEqual(managed_config["supervisor"], "null")
            self.assertEqual(managed_config["heartbeat"], "null")
            self.assertEqual(managed_config["local_client_required"], "pending")
        else:
            self.assertIn(managed_config["level"], {"supervised", "autonomous"})
            for field in ("goal_scope", "supervisor", "heartbeat"):
                self.assertNotIn(managed_config[field], {"", "null", "pending"})
            self.assertIn(managed_config["local_client_required"], {"true", "false"})

            goal_scope = managed_config["goal_scope"]
            if "#" in goal_scope:
                self.assertIn(goal_scope[0], {'"', "'"})
                self.assertEqual(goal_scope[-1], goal_scope[0])

        self.assertIn("github_agentic_workflows:", marker)
        self.assertIn("rollout: off", marker)
        self.assertIn("merge_capability: disabled", marker)

    def test_event_driven_profile_is_staged_and_merge_free(self) -> None:
        reference = (
            REPOSITORY / "skill" / "references" / "github-agentic-workflows.md"
        ).read_text(encoding="utf-8")
        assets = REPOSITORY / "skill" / "assets" / "github-agentic-workflows"
        supervisor = (assets / "agent-supervisor.md").read_text(encoding="utf-8")
        implementer = (assets / "agent-implement.md").read_text(encoding="utf-8")
        reviewer = (assets / "agent-review.md").read_text(encoding="utf-8")
        integrator = (assets / "agent-integrate.md").read_text(encoding="utf-8")

        self.assertIn("--apply", reference)
        self.assertIn("staged", reference)
        self.assertIn("agent:managed", reference)
        self.assertIn("dispatch-workflow", supervisor)
        self.assertIn("terminal handoff", supervisor)
        self.assertIn("After three failed cycles", supervisor)
        self.assertIn("Completed implementation must be non-draft before independent review", supervisor)
        self.assertIn("Never dispatch an approver-only role", supervisor)
        self.assertIn("repository-approved\n  current-head review signal", supervisor)
        self.assertIn("AGENT-CYCLE:", implementer)
        self.assertIn("needs:human", supervisor)
        self.assertEqual(supervisor.count("required-labels: [agent:managed]"), 3)
        self.assertIn("github.event.workflow_run.event == 'pull_request'", supervisor)
        self.assertIn("branches: [__CI_BRANCH_PATTERN__]", supervisor)
        self.assertIn("create-pull-request", implementer)
        self.assertIn("draft: false", implementer)
        self.assertIn("Never wait for review or approval before making completed work ready", implementer)
        self.assertIn("needs.pre_activation.outputs.managed_target_result", implementer)
        self.assertIn("needs: [managed-target-gate]", implementer)
        self.assertIn("Recheck managed target before writes", implementer)
        self.assertNotIn("allowed: [agent:managed", implementer)
        self.assertEqual(
            implementer.count('target: "${{ github.event.inputs.item_number }}"'), 4
        )
        self.assertEqual(implementer.count("required-labels: [agent:managed]"), 4)
        self.assertIn("submit-pull-request-review", reviewer)
        self.assertIn("repository-approved review signal", reviewer)
        self.assertIn("do not dispatch another approver-only Agent", reviewer)
        self.assertIn("Recheck managed pull request before writes", reviewer)
        self.assertIn("needs: [managed-target-gate]", reviewer)
        self.assertEqual(reviewer.count("required-labels: [agent:managed]"), 4)
        self.assertIn("needs: [managed-target-gate]", integrator)
        self.assertEqual(integrator.count("required-labels: [agent:managed]"), 3)
        self.assertIn("Never call a merge API", integrator)
        for content in (supervisor, implementer, reviewer, integrator):
            self.assertNotIn("merge-pull-request", content)

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
        self.assertIn("## Issue and PR state semantics", template)
        self.assertIn("`Ready for review` is a pull-request stage only", template)
        self.assertIn("Never send work back to the implementer solely", template)
        self.assertIn("Review gate: `<agent-review-signal|human-approval|both>`", template)
        self.assertIn("without waiting for review or approval", template)
        self.assertIn("Do not create another approver-only Agent", template)

    def test_in_review_requires_ready_for_review_not_pr_creation(self) -> None:
        template = (REPOSITORY / "templates" / "AGENTS.project.md").read_text(encoding="utf-8")
        readme = (REPOSITORY / "README.md").read_text(encoding="utf-8")
        skill = (REPOSITORY / "skill" / "SKILL.md").read_text(encoding="utf-8")
        automation = (
            REPOSITORY / "skill" / "references" / "github-project-automation.md"
        ).read_text(encoding="utf-8")
        daily_flow = (
            REPOSITORY / "skill" / "references" / "daily-project-flow.md"
        ).read_text(encoding="utf-8")
        managed_supervisor = (
            REPOSITORY / "skill" / "assets" / "codex-managed-supervisor.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("open and link a PR, move to `In review`", template)
        self.assertIn("mark the PR ready for formal review", template)
        self.assertNotIn("进入 PR → In review", readme)
        self.assertIn("PR Ready for review → In review", readme)
        self.assertNotIn("add them directly to `In review`", skill)
        self.assertNotIn("add the PR at `In review` rather than `Backlog`", automation)
        for content in (skill, automation):
            self.assertIn("non-draft and ready for formal review", content)
        self.assertIn("keep it draft and leave the Issue `In progress`", daily_flow)
        self.assertIn("Move the linked Issue to `In review`", daily_flow)
        self.assertIn("incomplete PR draft and its linked Issue `In progress`", managed_supervisor)
        self.assertIn("ready for formal review and move its linked Issue to `In review`", managed_supervisor)

    def test_review_starts_after_implementation_not_after_approval(self) -> None:
        skill = (REPOSITORY / "skill" / "SKILL.md").read_text(encoding="utf-8")
        daily_flow = (
            REPOSITORY / "skill" / "references" / "daily-project-flow.md"
        ).read_text(encoding="utf-8")
        managed = (
            REPOSITORY / "skill" / "references" / "managed-autopilot.md"
        ).read_text(encoding="utf-8")
        supervisor = (
            REPOSITORY / "skill" / "assets" / "codex-managed-supervisor.md"
        ).read_text(encoding="utf-8")
        event_supervisor = (
            REPOSITORY
            / "skill"
            / "assets"
            / "github-agentic-workflows"
            / "agent-supervisor.md"
        ).read_text(encoding="utf-8")
        template = (REPOSITORY / "templates" / "AGENTS.project.md").read_text(
            encoding="utf-8"
        )
        posix_installer = (REPOSITORY / "install.sh").read_text(encoding="utf-8")
        powershell_installer = (REPOSITORY / "install.ps1").read_text(encoding="utf-8")
        integrate_prompt = (REPOSITORY / "prompts" / "integrate.md").read_text(
            encoding="utf-8"
        )

        for content in (skill, daily_flow, supervisor, template, posix_installer, powershell_installer):
            self.assertIn("without waiting for review or approval", content)
        self.assertIn("overrides any generic publishing tool's draft-by-default convention", skill)
        self.assertIn("supervisor that observes the lag repairs it directly", managed)
        self.assertIn("repository-approved current-head review signal", integrate_prompt)
        self.assertNotIn("all required approvals", integrate_prompt)

        for content in (skill, daily_flow, managed, supervisor, template):
            self.assertIn("approver-only Agent", content)
        self.assertIn("approver-only role", event_supervisor)

        contradictory_rules = (
            "wait for approval before marking",
            "wait for review before marking",
            "review before marking the PR ready",
            "approval before marking the PR ready",
            "keep it draft until approval",
            "keep it draft until review",
        )
        for content in (
            skill,
            daily_flow,
            managed,
            supervisor,
            event_supervisor,
            template,
            posix_installer,
            powershell_installer,
        ):
            for contradiction in contradictory_rules:
                self.assertNotIn(contradiction, content.lower())


if __name__ == "__main__":
    unittest.main()
