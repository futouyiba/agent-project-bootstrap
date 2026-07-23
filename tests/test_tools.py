from __future__ import annotations

import importlib.util
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
GITHUB_PROJECT = "https://github.com/orgs/example/projects/1"
AGENTIC_ASSETS = REPOSITORY / "skill" / "assets" / "github-agentic-workflows"
LEGACY_PROFILE_V1 = REPOSITORY / "tests" / "fixtures" / "legacy-agentic-profile-v1"
LEGACY_PROFILE_V0 = REPOSITORY / "tests" / "fixtures" / "legacy-agentic-profile-v0"
LEGACY_WORKFLOW_NAMES = (
    "agent-supervisor.md",
    "agent-implement.md",
    "agent-review.md",
    "agent-integrate.md",
)


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def agentic_command(root: Path, *arguments: str) -> list[str]:
    return [
        sys.executable,
        str(AGENTIC),
        str(root),
        "--github-project",
        GITHUB_PROJECT,
        *arguments,
    ]


def install_legacy_staged_profile(root: Path, version: str = "v1") -> None:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    fixture_directory = {
        "v0": LEGACY_PROFILE_V0,
        "v1": LEGACY_PROFILE_V1,
    }[version]
    for name in LEGACY_WORKFLOW_NAMES:
        fixture = fixture_directory / name
        source = fixture if fixture.exists() else AGENTIC_ASSETS / name
        content = source.read_text(encoding="utf-8")
        # v1 predates the local MCP gateway exception added to the current
        # templates. The two unchanged v1 files use the current assets as a
        # compact fixture, so restore their exact historical content here.
        if version == "v1" and not fixture.exists():
            content = content.replace(
                "network:\n"
                "  allowed:\n"
                "    - defaults\n"
                "    # gh-aw routes MCP requests through the host-published gateway.\n"
                "    - host.docker.internal\n\n",
                "",
            )
        content = (
            content
            .replace("__ENGINE__", "codex")
            .replace("__STAGED__", "true")
            .replace("__CI_BRANCH_PATTERN__", json.dumps("**"))
            .replace("__CI_WORKFLOW__", json.dumps("CI"))
        )
        (workflows / name).write_text(content, encoding="utf-8")


def load_agentic_module():
    specification = importlib.util.spec_from_file_location(
        "configure_agentic_workflows_under_test",
        AGENTIC,
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


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
            result = run(agentic_command(root), root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["engine"], "codex")
            self.assertEqual(report["rollout"], "staged")
            self.assertEqual(report["required_secret"], "OPENAI_API_KEY")
            self.assertEqual(report["project_write_secret"], "GH_AW_WRITE_PROJECT_TOKEN")
            self.assertEqual(report["github_project"], GITHUB_PROJECT)
            self.assertTrue(all(item["action"] == "create" for item in report["files"]))
            self.assertFalse((root / ".github").exists())

    def test_apply_renders_five_workflows_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            command = agentic_command(root, "--engine", "codex", "--apply")
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
                self.assertNotIn("__GITHUB_PROJECT__", content)
            workflow_directory = workflows[0].parent
            reconcile = workflow_directory / "agent-reconcile-metadata.yml"
            self.assertTrue(reconcile.is_file())
            reconcile_content = reconcile.read_text(encoding="utf-8")
            for placeholder in (
                "__GITHUB_PROJECT__",
                "__GITHUB_PROJECT_OWNER__",
                "__GITHUB_PROJECT_NUMBER__",
            ):
                self.assertNotIn(placeholder, reconcile_content)
            self.assertIn('PROJECT_OWNER: "example"', reconcile_content)
            self.assertIn("PROJECT_NUMBER: 1", reconcile_content)
            self.assertIn(json.dumps(GITHUB_PROJECT), reconcile_content)

            supervisor = (workflow_directory / "agent-supervisor.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("agent-reconcile-metadata", supervisor)

            second = run(command, root)
            self.assertEqual(second.returncode, 0, second.stderr)
            report = json.loads(second.stdout)
            self.assertTrue(all(item["action"] == "unchanged" for item in report["files"]))

    def test_project_url_is_required_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)

            missing = run([sys.executable, str(AGENTIC), str(root)], root)
            invalid = run(
                [
                    sys.executable,
                    str(AGENTIC),
                    str(root),
                    "--github-project",
                    "https://github.com/example/not-a-project",
                ],
                root,
            )

            self.assertEqual(missing.returncode, 2)
            self.assertIn("--github-project", missing.stderr)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("GitHub Projects v2 URL", invalid.stderr)

    def test_exact_legacy_staged_profile_migrates_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root)
            workflows = root / ".github" / "workflows"
            before = {
                path.name: path.read_text(encoding="utf-8")
                for path in workflows.iterdir()
            }

            preview = run(agentic_command(root), root)

            self.assertEqual(preview.returncode, 0, preview.stderr)
            report = json.loads(preview.stdout)
            self.assertEqual(report["legacy_profile"], {"version": "v1", "staged": True})
            actions = {item["path"]: item["action"] for item in report["files"]}
            self.assertEqual(
                actions[".github/workflows/agent-supervisor.md"],
                "migrate_generated",
            )
            self.assertEqual(
                actions[".github/workflows/agent-review.md"],
                "migrate_generated",
            )
            self.assertEqual(
                actions[".github/workflows/agent-reconcile-metadata.yml"],
                "create",
            )
            self.assertEqual(
                before,
                {
                    path.name: path.read_text(encoding="utf-8")
                    for path in workflows.iterdir()
                },
            )

            applied = run(agentic_command(root, "--apply"), root)

            self.assertEqual(applied.returncode, 0, applied.stderr)
            self.assertTrue((workflows / "agent-reconcile-metadata.yml").is_file())
            final_report = json.loads(applied.stdout)
            self.assertIsNone(final_report["legacy_profile"])
            self.assertTrue(
                all(item["action"] == "unchanged" for item in final_report["files"])
            )

            second = run(agentic_command(root, "--apply"), root)

            self.assertEqual(second.returncode, 0, second.stderr)
            second_report = json.loads(second.stdout)
            self.assertFalse(second_report["recovered_transaction"])
            self.assertTrue(
                all(item["action"] == "unchanged" for item in second_report["files"])
            )

    def test_released_staged_profile_migrates_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root, "v0")

            preview = run(agentic_command(root), root)

            self.assertEqual(preview.returncode, 0, preview.stderr)
            report = json.loads(preview.stdout)
            self.assertEqual(report["legacy_profile"], {"version": "v0", "staged": True})
            actions = {item["path"]: item["action"] for item in report["files"]}
            self.assertEqual(
                actions[".github/workflows/agent-supervisor.md"],
                "migrate_generated",
            )

            applied = run(agentic_command(root, "--apply"), root)

            self.assertEqual(applied.returncode, 0, applied.stderr)
            final_report = json.loads(applied.stdout)
            self.assertIsNone(final_report["legacy_profile"])
            self.assertTrue(
                all(item["action"] == "unchanged" for item in final_report["files"])
            )

    def test_modified_legacy_profile_blocks_migration_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root)
            workflows = root / ".github" / "workflows"
            modified = workflows / "agent-supervisor.md"
            modified.write_text(
                modified.read_text(encoding="utf-8") + "\nuser change\n",
                encoding="utf-8",
            )
            before = {
                path.name: path.read_text(encoding="utf-8")
                for path in workflows.iterdir()
            }

            result = run(agentic_command(root, "--apply"), root)

            self.assertEqual(result.returncode, 3)
            self.assertEqual(
                before,
                {
                    path.name: path.read_text(encoding="utf-8")
                    for path in workflows.iterdir()
                },
            )
            self.assertFalse((workflows / "agent-reconcile-metadata.yml").exists())

    def test_legacy_staged_profile_must_migrate_before_live_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root)
            workflows = root / ".github" / "workflows"
            before = {
                path.name: path.read_text(encoding="utf-8")
                for path in workflows.iterdir()
            }

            result = run(agentic_command(root, "--live", "--apply"), root)

            self.assertEqual(result.returncode, 5)
            report = json.loads(result.stdout)
            self.assertEqual(report["legacy_profile"], {"version": "v1", "staged": True})
            actions = {item["path"]: item["action"] for item in report["files"]}
            self.assertEqual(
                actions[".github/workflows/agent-supervisor.md"],
                "requires_staged_migration",
            )
            self.assertEqual(
                actions[".github/workflows/agent-review.md"],
                "requires_staged_migration",
            )
            self.assertEqual(
                before,
                {
                    path.name: path.read_text(encoding="utf-8")
                    for path in workflows.iterdir()
                },
            )
            self.assertFalse((workflows / "agent-reconcile-metadata.yml").exists())

    def test_mid_migration_write_failure_rolls_back_and_retry_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root)
            workflows = root / ".github" / "workflows"
            before = {
                path.name: path.read_bytes()
                for path in workflows.iterdir()
            }
            module = load_agentic_module()
            report = module.plan(root, "codex", True, "**", "CI", GITHUB_PROJECT)
            writes = module.rendered_workflow_writes(
                root,
                report,
                "codex",
                True,
                "**",
                "CI",
                GITHUB_PROJECT,
            )
            replacements = 0

            def fail_on_second_replacement(source: Path, target: Path) -> None:
                nonlocal replacements
                replacements += 1
                if replacements == 2:
                    raise OSError("injected migration failure")
                os.replace(source, target)

            with self.assertRaises(module.WorkflowTransactionError):
                module.apply_workflow_transaction(
                    root,
                    writes,
                    replace_file=fail_on_second_replacement,
                )

            self.assertEqual(
                before,
                {
                    path.name: path.read_bytes()
                    for path in workflows.iterdir()
                },
            )
            self.assertFalse(module.workflow_transaction_directory(root).exists())

            retry = run(agentic_command(root, "--apply"), root)

            self.assertEqual(retry.returncode, 0, retry.stderr)
            retry_report = json.loads(retry.stdout)
            self.assertTrue(
                all(item["action"] == "unchanged" for item in retry_report["files"])
            )

    def test_manifest_parent_is_synced_before_target_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root)
            module = load_agentic_module()
            report = module.plan(root, "codex", True, "**", "CI", GITHUB_PROJECT)
            writes = module.rendered_workflow_writes(
                root,
                report,
                "codex",
                True,
                "**",
                "CI",
                GITHUB_PROJECT,
            )
            events: list[tuple[str, Path]] = []
            github = (root / ".github").resolve()
            transaction = module.workflow_transaction_directory(root)
            transaction_present_at_github_sync: list[bool] = []
            real_fsync_directory = module.fsync_directory
            real_atomic_write = module.atomic_write

            def record_sync(path: Path) -> None:
                resolved = path.resolve()
                events.append(("sync", resolved))
                if resolved == github:
                    transaction_present_at_github_sync.append(transaction.exists())
                real_fsync_directory(path)

            def record_atomic_write(target: Path, content: str) -> None:
                real_atomic_write(target, content)
                if target.name == module.TRANSACTION_MANIFEST_NAME:
                    events.append(("manifest", target.resolve()))

            def record_target_replacement(source: Path, target: Path) -> None:
                events.append(("replace", target.resolve()))
                os.replace(source, target)

            module.fsync_directory = record_sync
            module.atomic_write = record_atomic_write
            try:
                module.apply_workflow_transaction(
                    root,
                    writes,
                    replace_file=record_target_replacement,
                )
            finally:
                module.atomic_write = real_atomic_write
                module.fsync_directory = real_fsync_directory

            manifest_index = next(
                index for index, event in enumerate(events) if event[0] == "manifest"
            )
            replace_index = next(
                index for index, event in enumerate(events) if event[0] == "replace"
            )
            github_syncs = [
                index
                for index, event in enumerate(events)
                if event == ("sync", github)
            ]
            self.assertEqual(transaction_present_at_github_sync[:2], [True, True])
            self.assertTrue(any(index < manifest_index for index in github_syncs))
            self.assertTrue(
                any(manifest_index < index < replace_index for index in github_syncs)
            )

    def test_new_workflow_directories_sync_their_parents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            module = load_agentic_module()
            synced: list[Path] = []
            real_fsync_directory = module.fsync_directory

            def record_sync(path: Path) -> None:
                synced.append(path.resolve())
                real_fsync_directory(path)

            module.fsync_directory = record_sync
            try:
                module.ensure_destination(root)
            finally:
                module.fsync_directory = real_fsync_directory

            self.assertEqual(
                synced,
                [
                    root,
                    (root / ".github").resolve(),
                ],
            )

    def test_interrupted_migration_is_recovered_before_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root)
            module = load_agentic_module()
            report = module.plan(root, "codex", True, "**", "CI", GITHUB_PROJECT)
            writes = module.rendered_workflow_writes(
                root,
                report,
                "codex",
                True,
                "**",
                "CI",
                GITHUB_PROJECT,
            )
            transaction, entries = module.prepare_workflow_transaction(root, writes)
            first = entries[0]
            os.replace(
                transaction / str(first["staged"]),
                root / ".github" / "workflows" / str(first["name"]),
            )

            preview = run(agentic_command(root), root)

            self.assertEqual(preview.returncode, 7)
            self.assertEqual(
                json.loads(preview.stdout)["reason"],
                "pending_workflow_transaction",
            )
            self.assertTrue(transaction.exists())

            retry = run(agentic_command(root, "--apply"), root)

            self.assertEqual(retry.returncode, 0, retry.stderr)
            retry_report = json.loads(retry.stdout)
            self.assertTrue(retry_report["recovered_transaction"])
            self.assertTrue(
                all(item["action"] == "unchanged" for item in retry_report["files"])
            )
            self.assertFalse(transaction.exists())

    def test_concurrent_apply_is_rejected_without_repository_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            module = load_agentic_module()

            with module.workflow_transaction_lock(root):
                result = run(agentic_command(root, "--apply"), root)

            self.assertEqual(result.returncode, 7)
            self.assertEqual(
                json.loads(result.stdout)["reason"],
                "workflow_transaction_failed",
            )
            self.assertFalse((root / ".github").exists())

    def test_interrupted_migration_with_unknown_target_content_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            install_legacy_staged_profile(root)
            module = load_agentic_module()
            report = module.plan(root, "codex", True, "**", "CI", GITHUB_PROJECT)
            writes = module.rendered_workflow_writes(
                root,
                report,
                "codex",
                True,
                "**",
                "CI",
                GITHUB_PROJECT,
            )
            transaction, entries = module.prepare_workflow_transaction(root, writes)
            first_target = (
                root / ".github" / "workflows" / str(entries[0]["name"])
            )
            os.replace(
                transaction / str(entries[0]["staged"]),
                first_target,
            )
            first_target.write_text("unexpected concurrent edit\n", encoding="utf-8")

            result = run(agentic_command(root, "--apply"), root)

            self.assertEqual(result.returncode, 7)
            self.assertEqual(
                json.loads(result.stdout)["reason"],
                "workflow_transaction_failed",
            )
            self.assertEqual(
                first_target.read_text(encoding="utf-8"),
                "unexpected concurrent edit\n",
            )
            self.assertTrue(transaction.exists())

    def test_first_install_cannot_enable_live_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)

            result = run(agentic_command(root, "--live", "--apply"), root)

            self.assertEqual(result.returncode, 5)
            report = json.loads(result.stdout)
            self.assertEqual(len(report["blocked"]), 5)
            self.assertTrue(
                all(item["action"] == "requires_staged_install" for item in report["files"])
            )
            self.assertFalse((root / ".github").exists())

    def test_exact_staged_install_can_be_promoted_to_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            staged = run(agentic_command(root, "--apply"), root)
            self.assertEqual(staged.returncode, 0, staged.stderr)

            preview = run(agentic_command(root, "--live"), root)
            self.assertEqual(preview.returncode, 0, preview.stderr)
            actions = {
                item["path"]: item["action"]
                for item in json.loads(preview.stdout)["files"]
            }
            self.assertEqual(
                actions[".github/workflows/agent-reconcile-metadata.yml"],
                "unchanged",
            )
            self.assertTrue(
                all(
                    action == "promote_to_live"
                    for path, action in actions.items()
                    if path.endswith(".md")
                )
            )

            promoted = run(
                agentic_command(root, "--live", "--apply"), root
            )
            self.assertEqual(promoted.returncode, 0, promoted.stderr)
            for workflow in (root / ".github" / "workflows").glob("agent-*.md"):
                self.assertIn("staged: false", workflow.read_text(encoding="utf-8"))

    def test_modified_staged_install_cannot_be_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            self.assertEqual(
                run(agentic_command(root, "--apply"), root).returncode,
                0,
            )
            workflows = root / ".github" / "workflows"
            modified = workflows / "agent-review.md"
            modified.write_text(
                modified.read_text(encoding="utf-8") + "\nuser change\n", encoding="utf-8"
            )

            result = run(
                agentic_command(root, "--live", "--apply"), root
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

            result = run(agentic_command(root, "--apply"), root)

            self.assertEqual(result.returncode, 6)
            self.assertEqual(json.loads(result.stdout)["reason"], "unsafe_destination")
            self.assertEqual(list(outside.iterdir()), [])

    def test_symlinked_github_transaction_cleanup_is_rejected_without_external_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            container = Path(directory)
            root = container / "repository"
            outside = container / "outside"
            root.mkdir()
            outside.mkdir()
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            transaction = outside / ".agent-project-bootstrap-workflow-transaction"
            transaction.mkdir()
            sentinel = transaction / "preserve-me"
            sentinel.write_text("external content\n", encoding="utf-8")
            try:
                os.symlink(outside, root / ".github", target_is_directory=True)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"symbolic links unavailable: {error}")

            result = run(agentic_command(root, "--apply"), root)

            self.assertEqual(result.returncode, 6)
            self.assertEqual(json.loads(result.stdout)["reason"], "unsafe_destination")
            self.assertTrue(sentinel.is_file())
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "external content\n")

    def test_conflict_refuses_all_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(run(["git", "init", "-q"], root).returncode, 0)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            conflict = workflows / "agent-review.md"
            conflict.write_text("user-owned\n", encoding="utf-8")

            result = run(agentic_command(root, "--apply"), root)
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


@unittest.skipIf(os.name == "nt", "POSIX installer test")
class ClaudeInstallerTests(unittest.TestCase):
    def _install(self, claude_root: Path) -> subprocess.CompletedProcess[str]:
        return run(
            [
                "sh",
                str(REPOSITORY / "install.sh"),
                "--source",
                str(REPOSITORY),
                "--target",
                "claude",
                "--claude-home",
                str(claude_root),
                "--with-global-rule",
            ],
            REPOSITORY,
        )

    def test_claude_install_uses_commands_and_claude_md(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            claude_root = Path(directory) / "claude"

            first = self._install(claude_root)
            self.assertEqual(first.returncode, 0, first.stderr)

            destination = claude_root / "skills" / "agent-project-bootstrap"
            self.assertTrue((destination / "SKILL.md").exists())
            self.assertTrue((destination / "scripts" / "snapshot_github.py").exists())
            self.assertTrue(
                (destination / "assets" / "github-agentic-workflows" / "agent-supervisor.md").exists()
            )

            # Claude target installs a slash command, not a Codex prompt.
            integrate_command = claude_root / "commands" / "integrate.md"
            self.assertTrue(integrate_command.exists())
            command_text = integrate_command.read_text(encoding="utf-8")
            self.assertIn("$ARGUMENTS", command_text)
            self.assertNotIn("$$agent-project-bootstrap", command_text)
            self.assertIn("Do not deploy, publish", command_text)
            self.assertFalse((claude_root / "prompts").exists())

            rules_file = claude_root / "CLAUDE.md"
            self.assertTrue(rules_file.exists())
            rules = rules_file.read_text(encoding="utf-8")
            self.assertEqual(rules.count("<!-- agent-project-bootstrap:start -->"), 1)
            self.assertIn("one durable supervisor", rules)
            self.assertIn("repository `CLAUDE.md`", rules)
            self.assertIn("`/integrate`", rules)
            self.assertNotIn("/prompts:integrate", rules)

            # Idempotent re-install upgrades the managed block without duplicating it
            # and without backing up an identical command file.
            second = self._install(claude_root)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(
                rules_file.read_text(encoding="utf-8").count("<!-- agent-project-bootstrap:start -->"),
                1,
            )
            self.assertEqual(
                len(list((claude_root / "commands").glob("integrate.md.backup.*"))), 0
            )

    def test_claude_partial_marker_fails_without_losing_user_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            claude_root = Path(directory) / "claude"
            claude_root.mkdir(parents=True)
            rules_file = claude_root / "CLAUDE.md"
            original = "before\n<!-- agent-project-bootstrap:start -->\nstale rule\nafter\n"
            rules_file.write_text(original, encoding="utf-8")

            result = self._install(claude_root)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("markers are incomplete or duplicated", result.stderr)
            self.assertEqual(rules_file.read_text(encoding="utf-8"), original)


@unittest.skipIf(os.name == "nt", "POSIX installer test")
class PlaceholderLeakTests(unittest.TestCase):
    """The managed-block placeholder substitution must never touch user content
    outside the block, and must stay in sync between the codex and claude targets.
    """

    def test_placeholders_outside_managed_block_are_preserved(self) -> None:
        cases = [
            ("codex", "AGENTS.md", ["--codex-home"]),
            ("claude", "CLAUDE.md", ["--target", "claude", "--claude-home"]),
        ]
        for target, rules_name, home_flags in cases:
            with self.subTest(target=target):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory) / "home"
                    root.mkdir(parents=True)
                    rules = root / rules_name
                    user_line = "keep __INTEGRATE_COMMAND__ and __REPO_RULES_FILE__ verbatim"
                    rules.write_text("header line\n" + user_line + "\n", encoding="utf-8")

                    cmd = ["sh", str(REPOSITORY / "install.sh"), "--source", str(REPOSITORY)]
                    cmd += home_flags
                    cmd += [str(root), "--with-global-rule"]
                    result = run(cmd, REPOSITORY)

                    self.assertEqual(result.returncode, 0, result.stderr)
                    content = rules.read_text(encoding="utf-8")
                    # User content outside the managed block is byte-for-byte intact.
                    self.assertIn("header line", content)
                    self.assertIn(user_line, content)
                    # The managed block itself rendered to the target-correct value.
                    if target == "codex":
                        self.assertIn("`/prompts:integrate`", content)
                        self.assertIn("repository `AGENTS.md`", content)
                    else:
                        self.assertIn("`/integrate`", content)
                        self.assertIn("repository `CLAUDE.md`", content)


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
        reconciler = (assets / "agent-reconcile-metadata.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("--apply", reference)
        self.assertIn("staged", reference)
        self.assertIn("agent:managed", reference)
        self.assertIn("dispatch-workflow", supervisor)
        self.assertIn("terminal handoff", supervisor)
        self.assertIn("After three failed cycles", supervisor)
        self.assertIn("Completed implementation must be non-draft before independent review", supervisor)
        self.assertIn("Never dispatch an approver-only role", supervisor)
        self.assertIn("repository-approved\n  current-head review signal", supervisor)
        self.assertIn("agent-reconcile-metadata", supervisor)
        for workflow in (supervisor, implementer, reviewer, integrator):
            self.assertIn("network:\n  allowed:\n    - defaults\n", workflow)
            self.assertIn("    - host.docker.internal", workflow)
        self.assertNotIn("update-project:", supervisor)
        self.assertNotIn("GH_AW_WRITE_PROJECT_TOKEN", supervisor)
        self.assertIn("cannot accept an Agent-supplied Project URL", supervisor)
        self.assertIn("AGENT-CYCLE:", implementer)
        self.assertIn("needs:human", supervisor)
        self.assertEqual(supervisor.count("required-labels: [agent:managed]"), 3)
        self.assertIn(
            "allowed: [agent:needs-review, agent:needs-rework, needs:human]",
            supervisor,
        )
        self.assertIn(
            "allowed: [agent:needs-review, agent:needs-rework, needs:human]",
            supervisor,
        )
        self.assertIn(
            "After verifying that response resolves the exact recorded gate",
            supervisor,
        )
        self.assertNotIn("agent:merge-ready, needs:human]", supervisor)
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
        self.assertIn("allowed-events: [COMMENT]", reviewer)
        self.assertNotIn("allowed-events: [COMMENT, REQUEST_CHANGES]", reviewer)
        self.assertIn("Never submit\n`REQUEST_CHANGES`", reviewer)
        self.assertIn(
            "whether\nthe PR was authored by a human or by the same workflow identity",
            reviewer,
        )
        self.assertIn("managed label is the repository's author-agnostic blocking", reviewer)
        self.assertIn("repository-approved review signal", reviewer)
        self.assertIn("do not dispatch another approver-only Agent", reviewer)
        self.assertIn("Recheck managed pull request before writes", reviewer)
        self.assertIn("needs: [managed-target-gate]", reviewer)
        self.assertEqual(reviewer.count("required-labels: [agent:managed]"), 4)
        self.assertIn("needs: [managed-target-gate]", integrator)
        self.assertEqual(integrator.count("required-labels: [agent:managed]"), 3)
        self.assertIn("Never call a merge API", integrator)
        self.assertIn("closingIssuesReferences(first: 2)", reconciler)
        self.assertIn("totalCount", reconciler)
        self.assertIn('issues/$PR_NUMBER', reconciler)
        self.assertIn('<<<"$pr_issue_json"', reconciler)
        self.assertIn('.state == "open" and .merged == false', reconciler)
        self.assertIn('.state == "OPEN"', reconciler)
        self.assertIn('issues/$ISSUE_NUMBER', reconciler)
        self.assertIn("REPOSITORY_TOKEN: ${{ github.token }}", reconciler)
        self.assertIn("expected exactly one closing Issue", reconciler)
        self.assertIn("expected exactly one managed same-repository closing Issue", reconciler)
        self.assertIn("PROJECT_NUMBER: __GITHUB_PROJECT_NUMBER__", reconciler)
        self.assertIn("PROJECT_OWNER: __GITHUB_PROJECT_OWNER__", reconciler)
        self.assertIn("GH_AW_WRITE_PROJECT_TOKEN", reconciler)
        self.assertIn("expected exactly one configured Project item", reconciler)
        self.assertIn("expected exactly one In review option", reconciler)
        self.assertIn('gh api graphql --paginate', reconciler)
        self.assertIn(r'items(first: 100, after: \$endCursor)', reconciler)
        self.assertIn(r'fields(first: 100, after: \$endCursor)', reconciler)
        self.assertNotIn('gh project item-list', reconciler)
        self.assertNotIn('gh project field-list', reconciler)
        self.assertIn("gh pr ready", reconciler)
        self.assertIn("gh project item-edit", reconciler)
        self.assertNotIn("project_url", reconciler)
        self.assertNotIn("issue_number:", reconciler)
        for content in (supervisor, implementer, reviewer, integrator, reconciler):
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
        claude_template = (REPOSITORY / "templates" / "CLAUDE.project.md").read_text(
            encoding="utf-8"
        )
        claude_integrate_command = (
            REPOSITORY / "commands" / "integrate.md"
        ).read_text(encoding="utf-8")

        for content in (skill, daily_flow, supervisor, template, posix_installer, powershell_installer):
            self.assertIn("without waiting for review or approval", content)
        self.assertIn("overrides any generic publishing tool's draft-by-default convention", skill)
        self.assertIn("supervisor that observes the lag repairs it directly", managed)
        self.assertIn("repository-approved current-head review signal", integrate_prompt)
        self.assertNotIn("all required approvals", integrate_prompt)
        self.assertIn("repository-approved current-head review signal", claude_integrate_command)
        self.assertNotIn("all required approvals", claude_integrate_command)

        for content in (skill, daily_flow, managed, supervisor, template, claude_template):
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
            claude_template,
            posix_installer,
            powershell_installer,
        ):
            for contradiction in contradictory_rules:
                self.assertNotIn(contradiction, content.lower())

    def test_claude_project_template_contains_authorization_boundary(self) -> None:
        template = (REPOSITORY / "templates" / "CLAUDE.project.md").read_text(encoding="utf-8")
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
        self.assertIn("`/integrate`", template)
        self.assertIn("Claude Code", template)

    def test_claude_integrate_command_contract(self) -> None:
        command = (REPOSITORY / "commands" / "integrate.md").read_text(encoding="utf-8")
        self.assertIn("description:", command)
        self.assertIn("argument-hint:", command)
        self.assertIn("$ARGUMENTS", command)
        self.assertIn("explicit authorization for this turn", command)
        self.assertIn("dependenc", command)
        self.assertIn("Do not deploy, publish", command)


if __name__ == "__main__":
    unittest.main()
