---
description: Safely merge merge-ready PRs in dependency order
argument-hint: [optional scope]
---

Use $$agent-project-bootstrap in daily-flow integration mode.

Treat this invocation as explicit authorization for this turn to merge qualifying pull requests in the current repository. Apply this optional scope when supplied: $ARGUMENTS.

Fetch current GitHub state. Find open, non-draft PRs with the repository-approved current-head review signal and any separately configured platform approvals, order them by explicit dependencies, and process them one at a time. Before each merge, verify acceptance criteria, current required CI, mergeability, and unresolved review threads. Respect branch protection and the repository merge method. After each merge, refresh state before evaluating the next PR.

Skip anything that does not qualify and report the exact reason. Do not deploy, publish, create a release, delete tags, expand scope, or close work as Not planned.
