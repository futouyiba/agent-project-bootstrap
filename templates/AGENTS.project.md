# Project coordination

## Source of truth

- Use GitHub Issues and this repository's Project as mutable task state. Do not maintain a second editable task table.
- Treat `.codex/cache/github-snapshot.json` as a disposable read-only cache, never as task state.

## Repository workflow configuration

Bootstrap must replace every placeholder below with a discovered value, or write `pending` plus the reason before declaring setup complete.

- Project URL: `<project-url-or-pending>`
- Project automation: `<configured-or-pending-with-reason>`
- Exact status values:
  - Backlog: `<exact-value>`
  - Ready: `<exact-value>`
  - In progress: `<exact-value>`
  - Blocked: `<exact-value>`
  - In review: `<exact-value>`
  - Done: `<exact-value>`
- Validation commands:
  - Fast checks: `<command-or-pending>`
  - Full checks: `<command-or-pending>`
  - Build: `<command-or-not-applicable>`
- Review gate: `<agent-review-signal|human-approval|both>`
- Agent review signal: `<marker-provenance-and-stale-head-policy-or-not-applicable>`

## Natural-language intake

- The user does not need to know an Issue number. Search the fresh local snapshot and GitHub from their description.
- For one clear match, select it and report its number. For several plausible matches, show the best two or three and ask one question.
- Treat `记一下`, `收需求`, `开始做`, `收尾`, `合并收尾`, and `托管` as workflow shortcuts described by `agent-project-bootstrap`. Bare `托管` means the current repository and current explicit goal, active Issue, or active PR; ask only when that scope is ambiguous.

## Standing authorization

- For a clearly selected task, the agent may read GitHub state, move `Ready` to `In progress`, create a task branch, open and link a PR, record validation results, and, when implementation evidence is complete, mark the PR ready for formal review and move the linked Issue to `In review`.
- Ask before creating work not clearly implied by the conversation, changing scope or acceptance criteria, closing as `Not planned`, deleting records, merging, publishing, or deploying.
- `合并收尾` explicitly authorizes merging qualifying PRs for that turn only; it never authorizes deployment or publishing.
- Platform approval prompts still apply. A direct user request can grant narrower or broader authorization for that request.

## Issue and PR state semantics

- `Ready for review` is a pull-request stage only; do not create or require it as an Issue or Project status.
- Keep the linked Issue `In progress` while its PR is draft. When the PR is non-draft and ready for formal review, move the Issue to `In review` in the same handoff.
- Draft is only for genuinely incomplete work or early feedback. When implementation and scoped validation are complete, create a non-draft PR or mark it ready immediately without waiting for review or approval. This workflow overrides generic draft-by-default publishing behavior.
- Let the first authorized observer or the single managed supervisor reconcile missed metadata transitions. Never send work back to the implementer solely to change status.
- Return a PR to implementation only for code, tests, conflicts, unresolved review findings, or unmet acceptance criteria. The repository-approved current-head review signal, successful CI, and any separately configured platform approval hand it to the integration gate, subject to repository merge policy.
- The same independent reviewer that performs the substantive review publishes the final review signal. Do not create another approver-only Agent merely to repeat the verdict or click `Approve`; require a distinct approval identity only when the recorded repository or platform policy explicitly does so.

## Managed supervisor

Bootstrap must replace every placeholder below with an approved value, or write `pending` plus the reason. `off` is the safe default.

- Managed mode: `<off|supervised|autonomous>`
- Goal or Issue scope: `<scope-or-pending>`
- Supervisor: `<thread-automation-or-pending>`
- Heartbeat: `<schedule-or-pending>`
- Retry limit: `<integer-default-3>`
- Automatic review: `<configured-or-pending>`
- Merge policy: `<per_turn|qualified_auto_merge|manual>`
- Low-risk merge criteria: `<criteria-or-none>`
- High-risk paths or labels: `<paths-labels-or-none>`
- Human gates: `<repository-specific-gates-plus-skill-defaults>`
- Deployment and publishing: `<never-unless-explicitly-authorized>`

When managed mode is enabled, use one durable supervisor for this repository scope. On each heartbeat, refresh GitHub, resume active PRs before new work, address review and CI feedback, and notify the user only at a recorded human gate or after the retry limit. Do not require the user to relay messages between agent conversations.

## GitHub Agentic Workflows (optional)

Bootstrap must replace every placeholder below when the event-driven profile is approved. Keep it `off` otherwise.

- Enabled and rollout: `<off|staged|live>`
- Engine: `<codex|copilot|claude|gemini|pending>`
- Pinned `gh-aw` version: `<version-or-pending>`
- Required engine secret: `<secret-name-or-pending-never-the-value>`
- Supervisor schedule: `<schedule-or-pending>`
- Managed routing labels: `<exact-agent-labels-or-none>`
- Compiled lock files: `<committed|pending-with-reason>`
- Routine write policy: `<comments-labels-prs-and-same-branch-fixes-only>`
- Merge capability: `<disabled>`
- Deployment and publishing: `<never>`

When enabled, GitHub Agentic Workflows may route only items explicitly marked with the repository's managed label. The supervisor, implementer, reviewer, and merge-readiness checker communicate through current Issue/PR state. They may not infer merge, release, deployment, secret, billing, deletion, destructive migration, or scope-change authority. Start in `staged`, inspect proposed outputs and cost, then separately authorize `live` repository writes.

## Delivery

- Read the Issue, acceptance criteria, and dependencies before changing code.
- Do not expand scope silently; propose a follow-up Issue.
- Use a dedicated branch and pull request for each independently deliverable Issue.
- Run the repository's documented validation commands and report exact results.
- Do not merge while required checks fail, without the repository-approved current-head review signal, or without any separately configured platform approval.
