#!/usr/bin/env python3
"""Plan or install the optional GitHub Agentic Workflows profile.

This helper only writes repository-owned workflow source files. It never writes
secrets, compiles generated lock files implicitly, or overwrites a differing
workflow. The agent-project-bootstrap skill remains responsible for recording
repository policy in AGENTS.md and .codex/agent-project-bootstrap.yml.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


WORKFLOW_NAMES = (
    "agent-supervisor.md",
    "agent-implement.md",
    "agent-review.md",
    "agent-integrate.md",
)
SUPPORTED_ENGINES = ("codex", "copilot", "claude", "gemini")
TESTED_GH_AW_VERSION = "v0.82.14"


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


def detect_default_branch(repository: Path) -> str:
    candidates = (
        ["git", "-C", str(repository), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        ["git", "-C", str(repository), "branch", "--show-current"],
        ["git", "-C", str(repository), "config", "--get", "init.defaultBranch"],
    )
    for command in candidates:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        value = result.stdout.strip()
        if result.returncode == 0 and value:
            return value.removeprefix("origin/")
    return "main"


def render(source: Path, engine: str, staged: bool, default_branch: str, ci_workflow: str) -> str:
    return (
        source.read_text(encoding="utf-8")
        .replace("__ENGINE__", engine)
        .replace("__STAGED__", "true" if staged else "false")
        .replace("__DEFAULT_BRANCH__", json.dumps(default_branch))
        .replace("__CI_WORKFLOW__", json.dumps(ci_workflow))
    )


def plan(
    repository: Path, engine: str, staged: bool, default_branch: str, ci_workflow: str
) -> dict[str, object]:
    assets = Path(__file__).resolve().parents[1] / "assets" / "github-agentic-workflows"
    destination = repository / ".github" / "workflows"
    files: list[dict[str, str]] = []
    conflicts: list[str] = []

    for name in WORKFLOW_NAMES:
        source = assets / name
        target = destination / name
        content = render(source, engine, staged, default_branch, ci_workflow)
        if not target.exists():
            action = "create"
        elif target.read_text(encoding="utf-8") == content:
            action = "unchanged"
        else:
            action = "conflict"
            conflicts.append(str(target.relative_to(repository)))
        files.append({"path": str(target.relative_to(repository)), "action": action})

    return {
        "repository": str(repository),
        "engine": engine,
        "rollout": "staged" if staged else "live",
        "default_branch": default_branch,
        "ci_workflow": ci_workflow,
        "tested_gh_aw_version": TESTED_GH_AW_VERSION,
        "files": files,
        "conflicts": conflicts,
        "required_secret": "OPENAI_API_KEY" if engine == "codex" else "engine-specific",
        "next_steps": [
            "record the approved policy in AGENTS.md and .codex/agent-project-bootstrap.yml",
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
    parser.add_argument("--default-branch", help="Branch used to restrict CI completion events.")
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

    default_branch = args.default_branch or detect_default_branch(root)
    report = plan(root, args.engine, not args.live, default_branch, args.ci_workflow)
    if report["conflicts"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 3

    if args.compile and not args.apply:
        parser.error("--compile requires --apply")

    if args.apply:
        assets = Path(__file__).resolve().parents[1] / "assets" / "github-agentic-workflows"
        destination = root / ".github" / "workflows"
        destination.mkdir(parents=True, exist_ok=True)
        for name in WORKFLOW_NAMES:
            target = destination / name
            if not target.exists():
                target.write_text(
                    render(
                        assets / name,
                        args.engine,
                        not args.live,
                        default_branch,
                        args.ci_workflow,
                    ),
                    encoding="utf-8",
                )

        if args.compile:
            if shutil.which("gh") is None:
                print("gh is required for --compile", file=sys.stderr)
                return 4
            compiled = subprocess.run(["gh", "aw", "compile", "--strict"], cwd=root, check=False)
            if compiled.returncode != 0:
                return compiled.returncode
        report = plan(root, args.engine, not args.live, default_branch, args.ci_workflow)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
