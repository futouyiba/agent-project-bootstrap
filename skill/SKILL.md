---
name: agent-project-bootstrap
description: Interactively audit and initialize or migrate a Git repository for coordinated agent development. Use when starting or standardizing a project that needs GitHub Issues or Projects, pull-request rules, CI, branch protection, Codex worktrees, local environments, or multi-agent task coordination.
---

# Agent Project Bootstrap

Create a small, inspectable coordination layer around a repository. Keep durable policy in the repository, mutable work in GitHub, implementation in branches and pull requests, and objective validation in CI.

## Start with a read-only audit

1. Locate the Git root. If the current directory is not inside a Git repository, explain that this skill will not initialize Git unless the user explicitly asks.
2. Run `python3 scripts/audit_project.py [repository-path]`.
3. Treat the audit output as hints. Inspect existing project instructions and workflows before recommending changes.
4. Never print the contents of secret or environment files.
5. Determine whether this is a new repository or a running project with existing task and delivery conventions.

## Choose a profile interactively

If the user has not already selected a scope, offer one concise choice:

- **Coordination** — GitHub Issues/Projects conventions and issue/PR templates.
- **Delivery** — Coordination plus a stack-appropriate CI workflow and branch-protection checklist.
- **Worktree** — Delivery plus Codex local-environment and worktree-isolation guidance.

Default to **Delivery**. Skip the question when the user's request already determines the scope.

Before writing, show the exact files that would be created or changed. If the current request did not already authorize repository changes, wait for confirmation.

## Handle existing projects progressively

For a repository with existing tasks, branches, CI, or release rules, read [adopting an existing project](references/adopting-existing-project.md).

- Do not replace working conventions wholesale.
- Establish a dated cutover point and migrate only active work that still needs execution.
- Pilot the workflow on a small set of real issues.
- Make CI stable before making its checks mandatory.
- Archive old task lists as read-only references instead of maintaining two live systems.

## Apply the repository standard

Read [GitHub coordination](references/github-coordination.md) for the task model and suggested templates. Read [CI and branch protection](references/ci-and-protection.md) before creating a workflow. Read [worktree environment](references/worktree-environment.md) only for the Worktree profile.

Use these rules:

- Reuse and merge existing conventions. Never overwrite an existing `AGENTS.md`, issue template, pull-request template, or workflow wholesale.
- Put stable operating rules in root `AGENTS.md`. Keep them short and repository-specific.
- Put mutable task status, ownership, dependencies, and acceptance criteria in GitHub Issues/Projects rather than a shared JSON or Markdown task table.
- Use one branch and pull request per independently mergeable issue. Reference the issue from the pull request.
- Require deterministic checks for merge readiness. Human or agent review supplements CI; it does not replace CI.
- Create `.github/workflows/ci.yml` only when the stack and valid commands can be established from repository files or the user confirms them. Do not invent commands.
- Create `.worktreeinclude` only in the repository root and only for ignored local files that new Codex-managed worktrees genuinely need.
- Never include `.venv`, `node_modules`, build outputs, caches, database data directories, or broad secret directories in `.worktreeinclude`.
- Do not invent a `.codex` configuration format. Guide the user through the Codex desktop Local Environment UI, and add repository setup scripts only when appropriate.
- After a successful setup, create `.codex/agent-project-bootstrap.yml` with `version`, `profile`, `task_system`, and `initialized_at`. This marker records completion; it is not the task database.

## Use cached GitHub context carefully

Issue and PR records are not stored by Git in `.github/`. For low-latency read-only context, run `python3 scripts/snapshot_github.py status [repository-path]` and use a recent `.codex/cache/github-snapshot.json` when suitable.

Refresh with `python3 scripts/snapshot_github.py refresh [repository-path]` before external writes, merge decisions, assignments, or when freshness matters. Never edit or commit the cache as task state.

## Use connected services deliberately

If the GitHub connector/plugin is available, use it for reading or updating issues, projects, and pull-request context when authorized. If it is unavailable, produce exact manual steps or use an authenticated GitHub CLI when appropriate.

Do not assume installation means automatic use. Explicitly mention the connector when the task requires GitHub state. In ChatGPT, the user can invoke this skill as `@agent-project-bootstrap`; in Codex, as `$agent-project-bootstrap`.

## Finish with an actionable handoff

Report:

1. Files created or changed.
2. Existing files deliberately preserved.
3. GitHub web settings still required, especially Projects fields and branch protection.
4. The first issue to create and the checks expected on its pull request.
5. Any uncertainty that prevented a CI or worktree configuration from being generated.

