# GitHub coordination standard

## Source of truth

- **Issue**: outcome, scope, acceptance criteria, owner, dependencies, and discussion.
- **Project**: cross-issue status, priority, area, size or risk, and roadmap view.
- **Branch and pull request**: proposed implementation and review conversation.
- **CI check**: reproducible evidence that the change satisfies automated gates.
- **AGENTS.md**: stable repository instructions for agents and contributors.

Avoid a second mutable task database in Markdown, JSON, or YAML. A generated read-only summary is fine; two editable sources of truth are not.

## Minimal Project configuration

Use: `Backlog → Ready → In progress → Blocked or In review → Done`.

Add only fields that drive decisions: Priority, Area, Size, and Risk. Do not duplicate Project status as labels.

## Agent task issue contract

Every implementation-ready issue should state:

- observable outcome;
- relevant context and constraints;
- in scope and out of scope;
- testable acceptance criteria;
- validation commands or evidence;
- dependencies or blocked-by relationships;
- risk and rollback notes when relevant.

Use sub-issues for decomposition and GitHub dependency relationships for order. Keep ownership, status, and priority in GitHub metadata rather than rewriting the issue body.

## Pull-request contract

Ask for the linked issue, what changed and why, validation, visible evidence, risks, migrations, rollback, and excluded follow-up work. One PR should normally close one independently deliverable issue.

Installing a GitHub connector makes tools available; it does not automatically make GitHub the task system. Repository policy must say when the agent should read or update GitHub.

