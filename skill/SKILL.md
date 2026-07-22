---
name: agent-project-bootstrap
description: Initialize or migrate a Git repository for coordinated agent development, and operate its daily GitHub Issue, Project, pull-request, CI, and worktree flow from natural-language requests. Use when starting or standardizing a project, when the user describes work without an Issue number, or says 记一下, 收需求, 开始做, 收尾, or 合并收尾.
---

# Agent Project Workflow

Keep durable policy in the repository, mutable work in GitHub, implementation in branches and pull requests, and objective validation in CI. The user does not need to know Issue numbers or repeat the workflow contract.

## Select the mode

- Use **bootstrap mode first** whenever the repository has not adopted this workflow or the marker is absent, even when the same request contains a daily-flow shortcut. Preserve the pending task description; after authorized bootstrap completes, resolve it again and continue in daily-flow mode without making the user repeat it.
- Use **daily-flow mode** only after the repository is configured, or when an equivalent existing coordination policy is verified. If the user explicitly declines bootstrap, do not infer standing authorization from this skill.
- Installation makes this skill available; it does not configure a repository or a GitHub Project. Bootstrap each repository once.

## Bootstrap mode

### Start with a read-only audit

1. Locate the Git root. If the directory is not in a Git repository, do not initialize Git unless the user asks.
2. Run `python3 scripts/audit_project.py [repository-path]`.
3. Inspect existing project instructions and workflows. Treat audit output as hints.
4. Never print secret or environment-file contents.
5. Determine whether this is a new repository or a running project with existing conventions.

### Choose a profile

If scope is not already clear, offer one concise choice:

- **Coordination** — GitHub Issues/Projects conventions and Issue/PR templates.
- **Delivery** — Coordination plus stack-appropriate CI and a branch-protection checklist. This is the default.
- **Worktree** — Delivery plus Codex local-environment and worktree-isolation guidance.

Before writing, show the exact files to be changed. If the request did not authorize repository changes, wait for confirmation.

### Migrate progressively

For an established repository, read [adopting an existing project](references/adopting-existing-project.md).

- Preserve working conventions and establish a dated cutover.
- Migrate only active work that still needs execution.
- Pilot with a small set of real items.
- Stabilize CI before making it mandatory.
- Archive old task lists instead of maintaining two live systems.

### Apply repository policy

Read [GitHub coordination](references/github-coordination.md), [daily project flow](references/daily-project-flow.md), and [GitHub Project automation](references/github-project-automation.md). Read [CI and branch protection](references/ci-and-protection.md) before adding CI. Read [worktree environment](references/worktree-environment.md) only for the Worktree profile.

- Merge stable, repository-specific operating rules into root `AGENTS.md`; do not overwrite it.
- Put changing task state, ownership, dependencies, and acceptance criteria in GitHub, not a shared JSON or Markdown task table.
- Record the Project URL, exact status names, validation commands, and standing authorization in repository instructions.
- Reuse existing Issue templates, PR templates, and workflows. Do not replace them wholesale.
- Use one branch and pull request per independently mergeable Issue and link them.
- Add `.github/workflows/ci.yml` only when valid commands are established from the repository or confirmed by the user.
- Create `.worktreeinclude` only for ignored local files that new Codex worktrees need. Never include dependency trees, build outputs, caches, database data directories, or broad secret directories.
- Do not invent a `.codex` configuration format. Use the Codex desktop Local Environment UI where needed.

### Configure GitHub automation explicitly

Installing this skill does not create a Project or enable workflows. During bootstrap:

1. Detect the repository's existing Project and workflows.
2. Propose the minimal statuses `Backlog`, `Ready`, `In progress`, `Blocked`, `In review`, and `Done`.
3. With authorization and supported GitHub tools, configure deterministic automation: matching Issues are added, Issue or draft intake enters `Backlog`, and closed Issues enter `Done`. Keep PRs as linked delivery records by default; if the repository deliberately tracks PRs as Project items, add them directly to `In review` and move merged PRs to `Done`.
4. If the available tools cannot configure a setting, give the exact GitHub UI checklist and record it as pending rather than claiming success.

After successful setup, create or update `.codex/agent-project-bootstrap.yml` with `version`, `profile`, `task_system`, `workflow_mode`, `github_project`, `github_project_automation`, and `initialized_at`. This marker records configuration, not task state.

## Daily-flow mode

Read [daily project flow](references/daily-project-flow.md) and follow the repository's `AGENTS.md`.

### Resolve work from ordinary language

Never require the user to supply an Issue number.

1. Search a fresh local snapshot first when one exists.
2. Refresh or search GitHub when the cache is stale, no match is found, or a write decision needs current state.
3. If one match is clearly best, select it and report the number and title.
4. If several matches are plausible, show only the best two or three and ask one concise disambiguation question.
5. If none matches, create or propose an Issue according to the user's clear intent and the repository's standing authorization.

### Recognize short commands

- **记一下** — capture an uncertain idea as a Project draft item in `Backlog` when supported; do not silently turn speculation into committed work.
- **收需求** — extract, deduplicate, and search a batch of clear items; present one compact confirmation before creating anything not already authorized.
- **开始做 + natural-language description** — resolve the matching Issue, move it to `In progress`, create a branch, implement, validate, and open a linked PR when authorized.
- **收尾** — inspect the linked Issue, PR, review, and CI; record evidence and move to the appropriate status, but ask before merge, deployment, deletion, or other gated actions.
- **合并收尾 + optional scope** — treat the user's invocation as merge authorization for this turn only. Read the integration procedure in [daily project flow](references/daily-project-flow.md), merge only qualifying PRs in the current repository, and never deploy or publish.

### Apply standing authorization

Once a task is clearly selected and repository policy adopts this workflow, the agent may normally:

- read/search Issues, Projects, PRs, and CI;
- move the selected item from `Ready` to `In progress`;
- create its task branch;
- create and link a PR;
- move it to `In review`;
- record validation results.

Ask before:

- creating work not clearly implied by the conversation;
- changing scope or acceptance criteria;
- closing as `Not planned`;
- deleting records;
- merging a PR, unless the user explicitly invoked `合并收尾` or otherwise authorized the merge for this turn;
- publishing or deploying.

Repository policy may narrow this authorization. Tool and platform approval prompts still apply and cannot be bypassed.

## Use local GitHub context carefully

Issues and PRs are not stored by Git in `.github/`. Run `python3 scripts/snapshot_github.py status [repository-path]` to inspect `.codex/cache/github-snapshot.json`. Refresh before external writes, merge decisions, assignments, or whenever freshness matters. Never edit or commit the cache as task state.

## Use connected services deliberately

Use an available GitHub connector or authenticated GitHub CLI for current GitHub state. If neither is available, provide exact manual steps. Do not claim a remote action succeeded without verifying it.

## Finish with a compact handoff

Report changed files, preserved conventions, selected Issue/PR, validation and CI state, pending GitHub settings, and any action that still needs user approval.
