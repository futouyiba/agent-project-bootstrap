# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is a **collaboration specification distributed as a Skill for both Codex/ChatGPT and Claude Code**, not a runnable application. There is no runtime, no dependencies, and no build step. The deliverables are:

- a public Skill under `skill/` (one shared source, copied verbatim into either a user's `$CODEX_HOME/skills/agent-project-bootstrap` for Codex/ChatGPT or `~/.claude/skills/agent-project-bootstrap` for Claude Code);
- a Codex `/prompts:integrate` source under `prompts/integrate.md` (uses `$$agent-project-bootstrap` invocation) and a Claude Code `/integrate` slash command under `commands/integrate.md` (uses `$ARGUMENTS` placeholder); both are thin authorization shells — the real merge logic lives in the Skill's daily-flow integration procedure;
- three stdlib-only Python helper scripts under `skill/scripts/`;
- two cross-platform installers (`install.sh`, `install.ps1`) that take a `--target codex|claude` / `-Target` flag to select the destination client;
- Markdown templates and reference docs that bootstrap writes into target repositories (`templates/AGENTS.project.md` for Codex, `templates/CLAUDE.project.md` for Claude Code).

The product is a workflow contract: it moves "who does what, in what order, how it's accepted" out of chat history and into GitHub Issues/Projects, PRs, repository docs, and CI. See `README.md` for the user-facing explanation.

## Commands

Tests (Python 3.12 in CI; use `python` on Windows, `python3` elsewhere):

```sh
python3 -m unittest discover -s tests -v          # full suite
python3 tests/test_tools.py AuditTests -v          # one class
python3 tests/test_tools.py AgenticWorkflowConfiguratorTests -v   # another class
python3 tests/test_tools.py AuditTests.test_stack_and_coordination_detection   # one method
```

The test suite runs the scripts and installers as subprocesses, so it exercises the real CLI surface — keep it green before committing.

Smoke-test the installers into a throwaway home (do **not** point them at your real `~/.codex` or `~/.claude`). Default target is `codex`; pass `--target claude` / `-Target claude` for Claude Code:

```sh
./install.sh --source . --codex-home /tmp/agent-project-bootstrap-test --with-global-rule
./install.sh --source . --target claude --claude-home /tmp/agent-project-bootstrap-claude --with-global-rule
./install.ps1 -Source . -CodexHome "$env:TEMP\agent-project-bootstrap-test" -WithGlobalRule
./install.ps1 -Source . -Target claude -ClaudeHome "$env:TEMP\agent-project-bootstrap-claude" -WithGlobalRule
```

Running the scripts directly against any repository:

```sh
python3 skill/scripts/audit_project.py [path]                                    # read-only audit → JSON
python3 skill/scripts/snapshot_github.py refresh|status [path] [--limit N]        # needs `gh`
python3 skill/scripts/configure_agentic_workflows.py [repo] [flags]               # see contract below
```

CI (`.github/workflows/ci.yml`) runs the unittest suite plus installer smoke tests for **both the `codex` and `claude` targets** on `ubuntu-latest`, `macos-latest`, and `windows-latest`.

## Architecture

### One source of truth per kind of information

This is the central design rule and motivates most of the code's caution:

| Content | Authority |
|---|---|
| Requirements, tasks, dependencies, owners | GitHub Issue |
| Backlog, status, priority | GitHub Project |
| Stable agent/engineering rules | repository `AGENTS.md` (Codex) or `CLAUDE.md` (Claude Code) |
| Code changes, discussion, approval | Branch + Pull Request |
| Repeatable validation | CI / GitHub Actions |
| Bootstrap config marker | `.codex/agent-project-bootstrap.yml` |
| Disposable read-only cache | `.codex/cache/github-snapshot.json` (gitignored) |

**Never maintain a second editable task list** (no `tasks.md`/`tasks.json` synced with GitHub). `.codex/agent-project-bootstrap.yml` records *configuration only* (profile, status names, managed-mode settings) — never task state. The cache may be summarized but must not become a task database and is never committed.

### The Skill has three modes, selected by marker presence

`skill/SKILL.md` is the contract. Modes are **bootstrap** (first entry / migration; forced when `.codex/agent-project-bootstrap.yml` is absent), **daily-flow** (normal operation after bootstrap), and **managed** (a bounded supervisor; extends daily-flow, never unlimited). Bootstrap must run once per repository — installing the Skill alone configures nothing.

Natural-language shortcuts drive daily-flow without requiring Issue numbers: `记一下`, `收需求`, `开始做`, `收尾`, `合并收尾`, `托管`. These are referenced across `SKILL.md`, the installer-injected global rule (into `AGENTS.md` for Codex or `CLAUDE.md` for Claude Code), `templates/AGENTS.project.md` / `templates/CLAUDE.project.md`, and the tests.

### The authorization boundary is load-bearing

It is repeated (and must stay consistent) across the repository instruction file (`AGENTS.md` for Codex, `CLAUDE.md` for Claude Code), `SKILL.md`, `templates/AGENTS.project.md` / `templates/CLAUDE.project.md`, the global rule block in both installers, and the merge-shortcut sources (`prompts/integrate.md` for Codex, `commands/integrate.md` for Claude Code):

- For clearly selected work: reading GitHub, moving `Ready`→`In progress`, creating a branch + linked PR, moving to `In review`, and recording validation are allowed without asking.
- **Ask before**: scope/acceptance changes, closing as `Not planned`, deleting records, merging, publishing, deploying.
- `合并收尾` (and `/prompts:integrate` for Codex, `/integrate` for Claude Code) = merge authorization for **that turn only**, qualifying PRs in the current repo, never deploy/publish.
- Managed mode never authorizes deployment, publishing, deletion, destructive data changes, secrets/billing, scope expansion, or high-risk merges unless repository policy grants that exact action.
- The GitHub Agentic Workflows integrator is **merge-free** by design.

### Script CLI contracts (the actual "code")

`skill/scripts/audit_project.py` — read-only. Emits JSON on stdout. Exit `0` success, `2` when the path is not inside a Git repository (and writes nothing).

`skill/scripts/snapshot_github.py` — `refresh` (calls `gh`, atomically writes `.codex/cache/github-snapshot.json`) and `status` (reads the cache offline, reports age). Exit `0`/`1`.

`skill/scripts/configure_agentic_workflows.py` — plans/installs the optional `gh-aw` profile by rendering four workflow templates (`skill/assets/github-agentic-workflows/agent-{supervisor,implement,review,integrate}.md`) with placeholders `__ENGINE__`, `__STAGED__`, `__CI_BRANCH_PATTERN__`, `__CI_WORKFLOW__`. Exit codes are a tested contract:

- `0` ok · `2` not a Git repo · `3` conflict (existing file differs from both live and staged render; refuses all writes) · `4` `gh` missing for `--compile` · `5` first install cannot go `--live` (must start staged) · `6` unsafe destination (symlink or path escaping the repo).
- Promotion to live is allowed **only** when all four files exactly match the tool-generated staged version; any manual edit is preserved as a conflict. The configurator never writes secrets or lock files — `gh aw compile --strict` does, and its output is committed separately.

### Idempotent managed-block marker protocol

Both installers, when given `--with-global-rule`/`-WithGlobalRule`, inject/upgrade a rule block between HTML-comment markers `<!-- agent-project-bootstrap:start -->` and `<!-- agent-project-bootstrap:end -->`. For the `codex` target the block lives in `$CODEX_HOME/AGENTS.md` and its text references `/prompts:integrate` and `AGENTS.md`; for the `claude` target it lives in `~/.claude/CLAUDE.md` and references `/integrate` and `CLAUDE.md` (selected by `--target`/`-Target`). The block must have exactly one start and one end marker, each on its own line, in order. If those invariants are violated the installer **refuses to write and leaves the file unchanged** — this is enforced identically in `install.sh` (awk/grep/sed) and `install.ps1` (regex) and is the subject of several tests. Re-running upgrades only this block; existing installations and differing prompts/commands are backed up before replacement.

### The test suite pins documented behavior

`tests/test_tools.py` contains seven test classes:

- `AuditTests` — script behavior for non-repo and normal-repo scenarios.
- `SnapshotTests` — offline cache reading.
- `AgenticWorkflowConfiguratorTests` — plan, apply, idempotency, staged→live promotion, conflict detection, symlink rejection, and first-install live refusal.
- `PosixInstallerTests` — POSIX installer for the `codex` target (including marker-integrity edge cases).
- `ClaudeInstallerTests` — POSIX installer for the `claude` target (mirrors the codex tests, verifies `CLAUDE.md` and `/integrate` command placement).
- `PlaceholderLeakTests` — verifies that `__INTEGRATE_COMMAND__` and `__REPO_RULES_FILE__` substitution never touches user content outside the managed block, for both targets.
- `SkillContractTests` — asserts required strings in `SKILL.md`, the `references/*.md`, the `assets/github-agentic-workflows/*.md`, `templates/AGENTS.project.md`, `templates/CLAUDE.project.md`, `commands/integrate.md`, and `.codex/agent-project-bootstrap.yml` (e.g. `version: 5`, `merge_policy: per_turn`, no `merge-pull-request` in any worker, exact counts of `required-labels: [agent:managed]`).

**Editing any of those files can break the build** — update the tests in the same change when the contract intentionally evolves.

## Conventions (from `AGENTS.md`)

- Keep installers working on macOS, Linux, and Windows PowerShell.
- Scripts under `skill/scripts/` use **only the Python standard library**.
- Preserve existing user files during installation; back up an installed skill before replacing it.
- Keep the public `skill/` directory installable as-is.
- Resolve ordinary task descriptions without requiring the user to know an Issue number.
- GitHub Agentic Workflows stay opt-in and staged on first install; commit generated lock files; only typed safe outputs may write; the event-driven layer never gets merge/deploy/publish/secret/billing/delete authority.

## Platform notes

This machine is **macOS**. Use `python3` and `install.sh`; the PowerShell installer (`install.ps1`) is for Windows only. Absolute paths are preferred because `cd` in a compound command can trigger a permission prompt.

This repository dogfoods its own workflow: it has GitHub Agentic Workflows installed under `.github/workflows/agent-*.md` (source) and `.github/workflows/agent-*.lock.yml` (compiled), plus a dedicated `agentics-maintenance.yml` for CI maintenance. The `.codex/agent-project-bootstrap.yml` marker records its own bootstrap config (`version: 5`, `profile: delivery`). When making changes, treat these as live evidence that the contract works end-to-end.
