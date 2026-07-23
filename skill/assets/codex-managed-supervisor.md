Use `$agent-project-bootstrap` in managed mode for this repository and the goal recorded in repository policy.

On every heartbeat:

1. Refresh GitHub Issues, pull requests, review threads, required checks, dependencies, and Project state.
2. Resume active in-scope pull requests before starting new Ready work. Never duplicate an active branch or PR.
3. Reconcile state from current evidence: keep a genuinely incomplete PR draft and its linked Issue `In progress`; when implementation and scoped validation are complete, mark the PR ready for formal review and move its linked Issue to `In review` without waiting for review or approval. This overrides generic draft-by-default publishing behavior. `Ready for review` is a PR stage, not an Issue status. Never dispatch an implementer solely for a metadata update.
4. Address actionable review feedback and CI failures on the existing task branch, run the documented validation, push the fix, record evidence, and request re-review when supported.
5. Treat the independent reviewer's current-head final signal as the completed review handoff. Do not dispatch another approver-only Agent unless repository or platform policy explicitly requires a distinct GitHub approval identity.
6. If a pull request meets every repository merge gate and policy says `qualified_auto_merge`, enable auto-merge or enter the merge queue. Never deploy or publish.
7. If nothing is actionable, end this heartbeat quietly. Do not ask the user to copy status from another conversation.
8. Notify the user only when a documented human gate is reached or the configured retry limit is exhausted. First record a concise blocker and the exact decision needed on the linked Issue or PR.

Stay inside the configured goal and standing authorization. Never expand scope, delete records, change acceptance criteria, handle secrets or billing, perform destructive data changes, merge high-risk work, deploy, publish, or release without explicit authorization.
