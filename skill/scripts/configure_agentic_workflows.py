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
from pathlib import Path


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
    "v1": {
        "agent-supervisor.md": "a607c36fe04fad7f24fab44d630b5092c054472b1fab8cbfa2e3ef7daef5ae75",
        "agent-implement.md": "d9840f6166767b66073ae1e79acfc1f24a1139f695fc44c4482a1c1ca51b4de4",
        "agent-review.md": "1ab16035e1ab4fccfcda37ec8f413222c7a102b02ceffbe857d1fcda452bd3f3",
        "agent-integrate.md": "1257acc24865eaa93ce62e203fd8f25cea2a2feaeb36a8ff4bbc8f97fae1d6e0",
    },
}


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
        candidate.mkdir(exist_ok=True)
        if candidate.is_symlink() or not candidate.is_dir():
            raise UnsafeDestinationError(f"unsafe directory: {candidate}")
    return validate_destination(repository)


def atomic_write(target: Path, content: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


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

    root = git_root(Path(args.repository).resolve())
    if root is None:
        print(json.dumps({"reason": "not_git_repository"}, ensure_ascii=False, indent=2))
        return 2

    try:
        report = plan(
            root,
            args.engine,
            not args.live,
            args.ci_branch_pattern,
            args.ci_workflow,
            args.github_project,
        )
    except UnsafeDestinationError as error:
        print(json.dumps({"reason": "unsafe_destination", "detail": str(error)}, ensure_ascii=False, indent=2))
        return 6
    if report["conflicts"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 3
    if report["blocked"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 5

    if args.compile and not args.apply:
        parser.error("--compile requires --apply")

    if args.apply:
        assets = Path(__file__).resolve().parents[1] / "assets" / "github-agentic-workflows"
        try:
            destination = ensure_destination(root)
            actions = {item["path"]: item["action"] for item in report["files"]}
            for name in WORKFLOW_NAMES:
                target = destination / name
                relative = target.relative_to(root).as_posix()
                if actions[relative] in {
                    "create",
                    "promote_to_live",
                    "migrate_generated",
                }:
                    validate_destination(root)
                    atomic_write(
                        target,
                        render(
                            assets / name,
                            args.engine,
                            not args.live,
                            args.ci_branch_pattern,
                            args.ci_workflow,
                            args.github_project,
                        ),
                    )
        except UnsafeDestinationError as error:
            print(
                json.dumps({"reason": "unsafe_destination", "detail": str(error)}, ensure_ascii=False, indent=2)
            )
            return 6

        if args.compile:
            if shutil.which("gh") is None:
                print("gh is required for --compile", file=sys.stderr)
                return 4
            compiled = subprocess.run(["gh", "aw", "compile", "--strict"], cwd=root, check=False)
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

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
