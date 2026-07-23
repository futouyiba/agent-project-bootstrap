#!/usr/bin/env python3
"""Plan or install the optional GitHub Agentic Workflows profile.

This helper only writes repository-owned workflow source files. It never writes
secrets, compiles generated lock files implicitly, or overwrites a differing
workflow. An exact tool-generated staged set may be promoted to live. The
agent-project-bootstrap skill remains responsible for recording repository
policy in AGENTS.md and .codex/agent-project-bootstrap.yml.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


WORKFLOW_NAMES = (
    "agent-supervisor.md",
    "agent-implement.md",
    "agent-review.md",
    "agent-integrate.md",
    "agent-reconcile-metadata.yml",
)
LEGACY_WORKFLOW_NAMES = WORKFLOW_NAMES[:4]
SUPPORTED_ENGINES = ("codex", "copilot", "claude", "gemini")
TESTED_GH_AW_VERSION = "v0.82.14"
PROJECT_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<owner_kind>users|orgs)/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/"
    r"projects/(?P<number>[1-9][0-9]*)"
)
LEGACY_PROFILE_TEMPLATE_HASHES = {
    # v0 is the staged profile released on main before the metadata reconciler
    # and recoverable migration support. Keep it recognizable so pristine
    # installations receive the same atomic upgrade path as later profiles.
    "v0": {
        "agent-supervisor.md": "bcb7e73e50e0c4a586c2d97d1e755c17c82ece86ec7fc83732139621722a248a",
        "agent-implement.md": "7386153631ca960f7610406456f28d806ff27dcd7ca63f271b7ab7ba051bcf1a",
        "agent-review.md": "11bd78faa9a8e60bb17f89362447051a76e28196e7c310a279d31dde8a511bd3",
        "agent-integrate.md": "1257acc24865eaa93ce62e203fd8f25cea2a2feaeb36a8ff4bbc8f97fae1d6e0",
    },
    "v1": {
        "agent-supervisor.md": "a607c36fe04fad7f24fab44d630b5092c054472b1fab8cbfa2e3ef7daef5ae75",
        "agent-implement.md": "d9840f6166767b66073ae1e79acfc1f24a1139f695fc44c4482a1c1ca51b4de4",
        "agent-review.md": "1ab16035e1ab4fccfcda37ec8f413222c7a102b02ceffbe857d1fcda452bd3f3",
        "agent-integrate.md": "1257acc24865eaa93ce62e203fd8f25cea2a2feaeb36a8ff4bbc8f97fae1d6e0",
    },
}
TRANSACTION_DIRECTORY_NAME = ".agent-project-bootstrap-workflow-transaction"
TRANSACTION_MANIFEST_NAME = "manifest.json"
TRANSACTION_VERSION = 1


def git_root(path: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


class UnsafeDestinationError(ValueError):
    pass


class WorkflowTransactionError(RuntimeError):
    pass


def is_within(path: Path, repository: Path) -> bool:
    try:
        path.relative_to(repository)
    except ValueError:
        return False
    return True


def validate_destination(repository: Path) -> Path:
    repository = repository.resolve(strict=True)
    destination = repository / ".github" / "workflows"
    for candidate in (repository / ".github", destination):
        if candidate.is_symlink():
            raise UnsafeDestinationError(f"refusing symbolic link: {candidate}")
        if candidate.exists() and not candidate.is_dir():
            raise UnsafeDestinationError(f"expected directory: {candidate}")
        if not is_within(candidate.resolve(strict=False), repository):
            raise UnsafeDestinationError(f"path escapes repository: {candidate}")

    for name in WORKFLOW_NAMES:
        target = destination / name
        if target.is_symlink():
            raise UnsafeDestinationError(f"refusing symbolic link: {target}")
        if not is_within(target.resolve(strict=False), repository):
            raise UnsafeDestinationError(f"path escapes repository: {target}")
    return destination


def ensure_destination(repository: Path) -> Path:
    for candidate in (repository / ".github", repository / ".github" / "workflows"):
        existed = candidate.exists()
        candidate.mkdir(exist_ok=True)
        if candidate.is_symlink() or not candidate.is_dir():
            raise UnsafeDestinationError(f"unsafe directory: {candidate}")
        if not existed:
            fsync_directory(candidate.parent)
    return validate_destination(repository)


def atomic_write(target: Path, content: str) -> None:
    atomic_write_bytes(target, content.encode("utf-8"))


def atomic_write_bytes(target: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
        fsync_directory(target.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def workflow_transaction_directory(repository: Path) -> Path:
    return repository.resolve(strict=True) / ".github" / TRANSACTION_DIRECTORY_NAME


@contextmanager
def workflow_transaction_lock(repository: Path) -> Iterator[None]:
    identity = hashlib.sha256(str(repository.resolve()).encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"agent-project-bootstrap-{identity}.lock"
    try:
        descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as error:
        raise WorkflowTransactionError(
            "cannot open the workflow transaction lock"
        ) from error
    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt

                if os.fstat(descriptor).st_size == 0:
                    os.write(descriptor, b"0")
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as error:
            raise WorkflowTransactionError(
                "another configurator process holds the workflow transaction lock"
            ) from error
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def cleanup_workflow_transaction(transaction: Path) -> None:
    if transaction.is_symlink():
        raise WorkflowTransactionError(
            f"refusing symbolic-link transaction directory: {transaction}"
        )
    if transaction.exists():
        shutil.rmtree(transaction)
        fsync_directory(transaction.parent)


def load_workflow_transaction(
    repository: Path,
) -> tuple[Path, list[dict[str, object]]] | None:
    transaction = workflow_transaction_directory(repository)
    if not transaction.exists():
        return None
    if transaction.is_symlink() or not transaction.is_dir():
        raise WorkflowTransactionError(f"unsafe workflow transaction path: {transaction}")

    manifest_path = transaction / TRANSACTION_MANIFEST_NAME
    if not manifest_path.exists():
        cleanup_workflow_transaction(transaction)
        return None
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise WorkflowTransactionError(f"unsafe workflow transaction manifest: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkflowTransactionError(
            f"cannot read workflow transaction manifest: {manifest_path}"
        ) from error
    if (
        not isinstance(manifest, dict)
        or manifest.get("version") != TRANSACTION_VERSION
        or not isinstance(manifest.get("files"), list)
    ):
        raise WorkflowTransactionError(f"invalid workflow transaction manifest: {manifest_path}")

    entries = manifest["files"]
    names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise WorkflowTransactionError("invalid workflow transaction entry")
        name = entry.get("name")
        existed = entry.get("existed")
        old_hash = entry.get("old_sha256")
        new_hash = entry.get("new_sha256")
        backup = entry.get("backup")
        staged = entry.get("staged")
        if (
            not isinstance(name, str)
            or name not in WORKFLOW_NAMES
            or name in names
            or not isinstance(existed, bool)
            or (existed and not isinstance(old_hash, str))
            or (not existed and old_hash is not None)
            or not isinstance(new_hash, str)
            or (existed and not isinstance(backup, str))
            or (not existed and backup is not None)
            or not isinstance(staged, str)
        ):
            raise WorkflowTransactionError("invalid workflow transaction entry")
        for artifact in (backup, staged):
            if artifact is None:
                continue
            artifact_path = transaction / artifact
            if (
                Path(artifact).name != artifact
                or artifact_path.is_symlink()
                or not is_within(artifact_path.resolve(strict=False), transaction)
            ):
                raise WorkflowTransactionError("unsafe workflow transaction artifact")
        names.add(name)
    return transaction, entries


def recover_workflow_transaction(repository: Path) -> bool:
    try:
        return _recover_workflow_transaction(repository)
    except WorkflowTransactionError:
        raise
    except OSError as error:
        raise WorkflowTransactionError(
            "could not recover the pending workflow transaction"
        ) from error


def _recover_workflow_transaction(repository: Path) -> bool:
    # Validate the repository-owned destination before looking for or cleaning a
    # transaction.  Otherwise an untrusted `.github` symlink could make the
    # missing-manifest cleanup below remove files outside the repository.
    destination = validate_destination(repository)
    loaded = load_workflow_transaction(repository)
    if loaded is None:
        return False
    transaction, entries = loaded

    for entry in entries:
        name = str(entry["name"])
        target = destination / name
        existed = bool(entry["existed"])
        old_hash = entry["old_sha256"]
        new_hash = str(entry["new_sha256"])
        current = target.read_bytes() if target.exists() else None
        current_hash = sha256_bytes(current) if current is not None else None

        if existed:
            if current_hash == old_hash:
                continue
            if current_hash != new_hash:
                raise WorkflowTransactionError(
                    f"cannot recover workflow with unexpected content: {target}"
                )
            backup_path = transaction / str(entry["backup"])
            if not backup_path.is_file() or backup_path.is_symlink():
                raise WorkflowTransactionError(f"missing workflow transaction backup: {target}")
            backup = backup_path.read_bytes()
            if sha256_bytes(backup) != old_hash:
                raise WorkflowTransactionError(f"invalid workflow transaction backup: {target}")
            atomic_write_bytes(target, backup)
        else:
            if current is None:
                continue
            if current_hash != new_hash:
                raise WorkflowTransactionError(
                    f"cannot recover newly created workflow with unexpected content: {target}"
                )
            target.unlink()
            fsync_directory(destination)

    cleanup_workflow_transaction(transaction)
    return True


def prepare_workflow_transaction(
    repository: Path,
    writes: list[tuple[Path, str]],
) -> tuple[Path, list[dict[str, object]]]:
    if not writes:
        raise WorkflowTransactionError("cannot prepare an empty workflow transaction")
    destination = ensure_destination(repository)
    transaction = workflow_transaction_directory(repository)
    if transaction.exists():
        raise WorkflowTransactionError(
            "pending workflow transaction must be recovered before applying"
        )

    transaction.mkdir()
    fsync_directory(transaction.parent)
    entries: list[dict[str, object]] = []
    try:
        names: set[str] = set()
        for index, (target, content) in enumerate(writes):
            if (
                target.parent != destination
                or target.name not in WORKFLOW_NAMES
                or target.name in names
                or target.is_symlink()
            ):
                raise WorkflowTransactionError(f"invalid workflow transaction target: {target}")
            names.add(target.name)
            old = target.read_bytes() if target.exists() else None
            new = content.encode("utf-8")
            staged_name = f"{index:02d}-{target.name}.staged"
            backup_name = f"{index:02d}-{target.name}.backup" if old is not None else None
            atomic_write_bytes(transaction / staged_name, new)
            if backup_name is not None:
                atomic_write_bytes(transaction / backup_name, old)
            entries.append(
                {
                    "name": target.name,
                    "existed": old is not None,
                    "old_sha256": sha256_bytes(old) if old is not None else None,
                    "new_sha256": sha256_bytes(new),
                    "backup": backup_name,
                    "staged": staged_name,
                }
            )

        atomic_write(
            transaction / TRANSACTION_MANIFEST_NAME,
            json.dumps(
                {"version": TRANSACTION_VERSION, "files": entries},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        fsync_directory(transaction.parent)
    except BaseException as error:
        try:
            cleanup_workflow_transaction(transaction)
        except BaseException as cleanup_error:
            raise WorkflowTransactionError(
                "workflow transaction preparation failed and cleanup is incomplete"
            ) from cleanup_error
        raise WorkflowTransactionError("could not prepare workflow transaction") from error
    return transaction, entries


def apply_workflow_transaction(
    repository: Path,
    writes: list[tuple[Path, str]],
    replace_file: Callable[[Path, Path], None] = os.replace,
) -> None:
    if not writes:
        return
    destination = ensure_destination(repository)
    transaction, entries = prepare_workflow_transaction(repository, writes)
    try:
        for entry in entries:
            staged = transaction / str(entry["staged"])
            target = destination / str(entry["name"])
            current = target.read_bytes() if target.exists() else None
            current_hash = sha256_bytes(current) if current is not None else None
            if current_hash != entry["old_sha256"]:
                raise WorkflowTransactionError(
                    f"workflow changed after transaction preparation: {target}"
                )
            replace_file(staged, target)
            fsync_directory(destination)
    except BaseException as error:
        try:
            recover_workflow_transaction(repository)
        except BaseException as recovery_error:
            raise WorkflowTransactionError(
                "workflow transaction failed and automatic rollback is incomplete"
            ) from recovery_error
        raise WorkflowTransactionError(
            "workflow transaction failed and all target files were rolled back"
        ) from error

    manifest = transaction / TRANSACTION_MANIFEST_NAME
    try:
        manifest.unlink()
        cleanup_workflow_transaction(transaction)
    except OSError as error:
        raise WorkflowTransactionError(
            "workflows were committed but transaction cleanup is incomplete; "
            "rerun with --apply to verify and clean up"
        ) from error


def github_project_url(value: str) -> str:
    if PROJECT_URL_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "expected a GitHub Projects v2 URL such as "
            "https://github.com/orgs/example/projects/1"
        )
    return value


def canonicalize_rendered_workflow(
    content: str,
    engine: str,
    staged: bool,
    ci_branch_pattern: str,
    ci_workflow: str,
    github_project: str,
) -> str:
    replacements = (
        (f"\nengine: {engine}\n", "\nengine: __ENGINE__\n"),
        (
            f"\n  staged: {'true' if staged else 'false'}\n",
            "\n  staged: __STAGED__\n",
        ),
        (
            f"\n    workflows: [{json.dumps(ci_workflow)}]\n",
            "\n    workflows: [__CI_WORKFLOW__]\n",
        ),
        (
            f"\n    branches: [{json.dumps(ci_branch_pattern)}]\n",
            "\n    branches: [__CI_BRANCH_PATTERN__]\n",
        ),
        (
            f"\n    project: {json.dumps(github_project)}\n",
            "\n    project: __GITHUB_PROJECT__\n",
        ),
    )
    for rendered, placeholder in replacements:
        content = content.replace(rendered, placeholder)
    return content


def detect_legacy_profile(
    destination: Path,
    engine: str,
    ci_branch_pattern: str,
    ci_workflow: str,
    github_project: str,
) -> dict[str, object] | None:
    for version, expected_hashes in LEGACY_PROFILE_TEMPLATE_HASHES.items():
        for legacy_staged in (True, False):
            matched = True
            for name, expected_hash in expected_hashes.items():
                target = destination / name
                if not target.is_file():
                    matched = False
                    break
                canonical = canonicalize_rendered_workflow(
                    target.read_text(encoding="utf-8"),
                    engine,
                    legacy_staged,
                    ci_branch_pattern,
                    ci_workflow,
                    github_project,
                )
                actual_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                if actual_hash != expected_hash:
                    matched = False
                    break
            if matched:
                return {"version": version, "staged": legacy_staged}
    return None


def render(
    source: Path,
    engine: str,
    staged: bool,
    ci_branch_pattern: str,
    ci_workflow: str,
    github_project: str,
) -> str:
    project_match = PROJECT_URL_PATTERN.fullmatch(github_project)
    if project_match is None:
        raise ValueError(f"invalid GitHub Project URL: {github_project}")
    return (
        source.read_text(encoding="utf-8")
        .replace("__ENGINE__", engine)
        .replace("__STAGED__", "true" if staged else "false")
        .replace("__CI_BRANCH_PATTERN__", json.dumps(ci_branch_pattern))
        .replace("__CI_WORKFLOW__", json.dumps(ci_workflow))
        .replace("__GITHUB_PROJECT__", json.dumps(github_project))
        .replace("__GITHUB_PROJECT_OWNER__", json.dumps(project_match["owner"]))
        .replace("__GITHUB_PROJECT_NUMBER__", project_match["number"])
    )


def plan(
    repository: Path,
    engine: str,
    staged: bool,
    ci_branch_pattern: str,
    ci_workflow: str,
    github_project: str,
) -> dict[str, object]:
    repository = repository.resolve(strict=True)
    assets = Path(__file__).resolve().parents[1] / "assets" / "github-agentic-workflows"
    destination = validate_destination(repository)
    files: list[dict[str, str]] = []
    conflicts: list[str] = []
    blocked: list[str] = []
    legacy_profile = detect_legacy_profile(
        destination,
        engine,
        ci_branch_pattern,
        ci_workflow,
        github_project,
    )

    for name in WORKFLOW_NAMES:
        source = assets / name
        target = destination / name
        content = render(
            source,
            engine,
            staged,
            ci_branch_pattern,
            ci_workflow,
            github_project,
        )
        staged_content = render(
            source,
            engine,
            True,
            ci_branch_pattern,
            ci_workflow,
            github_project,
        )
        if not target.exists():
            if staged:
                action = "create"
            else:
                action = "requires_staged_install"
                blocked.append(target.relative_to(repository).as_posix())
        elif target.read_text(encoding="utf-8") == content:
            action = "unchanged"
        elif not staged and target.read_text(encoding="utf-8") == staged_content:
            action = "promote_to_live"
        elif legacy_profile and name in LEGACY_WORKFLOW_NAMES:
            relative = target.relative_to(repository).as_posix()
            if legacy_profile["staged"] and staged:
                action = "migrate_generated"
            elif legacy_profile["staged"]:
                action = "requires_staged_migration"
                blocked.append(relative)
            else:
                action = "legacy_live_requires_manual_review"
                blocked.append(relative)
        else:
            action = "conflict"
            conflicts.append(target.relative_to(repository).as_posix())
        files.append(
            {"path": target.relative_to(repository).as_posix(), "action": action}
        )

    return {
        "repository": str(repository),
        "engine": engine,
        "rollout": "staged" if staged else "live",
        "ci_branch_pattern": ci_branch_pattern,
        "ci_workflow": ci_workflow,
        "github_project": github_project,
        "tested_gh_aw_version": TESTED_GH_AW_VERSION,
        "files": files,
        "legacy_profile": legacy_profile,
        "recovered_transaction": False,
        "conflicts": conflicts,
        "blocked": blocked,
        "required_secret": "OPENAI_API_KEY" if engine == "codex" else "engine-specific",
        "project_write_secret": "GH_AW_WRITE_PROJECT_TOKEN",
        "next_steps": [
            "record the approved policy in AGENTS.md and .codex/agent-project-bootstrap.yml",
            "configure the documented least-privilege Project write token",
            "create the documented agent:* repository labels",
            "compile and commit generated lock files with gh aw compile --strict",
            "run staged trials before changing rollout to live",
        ],
    }


def rendered_workflow_writes(
    repository: Path,
    report: dict[str, object],
    engine: str,
    staged: bool,
    ci_branch_pattern: str,
    ci_workflow: str,
    github_project: str,
) -> list[tuple[Path, str]]:
    repository = repository.resolve(strict=True)
    assets = Path(__file__).resolve().parents[1] / "assets" / "github-agentic-workflows"
    destination = ensure_destination(repository)
    actions = {
        str(item["path"]): str(item["action"])
        for item in report["files"]
        if isinstance(item, dict)
    }
    writes: list[tuple[Path, str]] = []
    for name in WORKFLOW_NAMES:
        target = destination / name
        relative = target.relative_to(repository).as_posix()
        if actions.get(relative) in {
            "create",
            "promote_to_live",
            "migrate_generated",
        }:
            writes.append(
                (
                    target,
                    render(
                        assets / name,
                        engine,
                        staged,
                        ci_branch_pattern,
                        ci_workflow,
                        github_project,
                    ),
                )
            )
    return writes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plan or install the optional GitHub Agentic Workflows profile."
    )
    parser.add_argument("repository", nargs="?", default=".")
    parser.add_argument("--engine", choices=SUPPORTED_ENGINES, default="codex")
    parser.add_argument(
        "--github-project",
        required=True,
        type=github_project_url,
        help="Exact GitHub Projects v2 URL whose Issue status the supervisor may update.",
    )
    parser.add_argument(
        "--ci-branch-pattern",
        default="**",
        help="GitHub branch glob for PR-head CI workflow_run events (default: **).",
    )
    parser.add_argument("--ci-workflow", default="CI", help="Existing GitHub Actions CI workflow name.")
    parser.add_argument("--live", action="store_true", help="Enable real safe outputs instead of previews.")
    parser.add_argument("--apply", action="store_true", help="Create absent workflow source files.")
    parser.add_argument(
        "--compile",
        action="store_true",
        help="After applying, run the installed `gh aw compile --strict` command.",
    )
    args = parser.parse_args()
    if args.compile and not args.apply:
        parser.error("--compile requires --apply")

    root = git_root(Path(args.repository).resolve())
    if root is None:
        print(json.dumps({"reason": "not_git_repository"}, ensure_ascii=False, indent=2))
        return 2

    try:
        with workflow_transaction_lock(root):
            transaction = workflow_transaction_directory(root)
            if not args.apply and transaction.exists():
                print(
                    json.dumps(
                        {
                            "reason": "pending_workflow_transaction",
                            "detail": "rerun with --apply to recover before planning",
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return 7
            recovered_transaction = (
                recover_workflow_transaction(root) if args.apply else False
            )
            report = plan(
                root,
                args.engine,
                not args.live,
                args.ci_branch_pattern,
                args.ci_workflow,
                args.github_project,
            )
            report["recovered_transaction"] = recovered_transaction
            if report["conflicts"]:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 3
            if report["blocked"]:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 5

            if args.apply:
                writes = rendered_workflow_writes(
                    root,
                    report,
                    args.engine,
                    not args.live,
                    args.ci_branch_pattern,
                    args.ci_workflow,
                    args.github_project,
                )
                apply_workflow_transaction(root, writes)

                if args.compile:
                    if shutil.which("gh") is None:
                        print("gh is required for --compile", file=sys.stderr)
                        return 4
                    compiled = subprocess.run(
                        ["gh", "aw", "compile", "--strict"],
                        cwd=root,
                        check=False,
                    )
                    if compiled.returncode != 0:
                        return compiled.returncode
                report = plan(
                    root,
                    args.engine,
                    not args.live,
                    args.ci_branch_pattern,
                    args.ci_workflow,
                    args.github_project,
                )
                report["recovered_transaction"] = recovered_transaction
    except UnsafeDestinationError as error:
        print(
            json.dumps(
                {"reason": "unsafe_destination", "detail": str(error)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 6
    except WorkflowTransactionError as error:
        print(
            json.dumps(
                {"reason": "workflow_transaction_failed", "detail": str(error)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 7

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
