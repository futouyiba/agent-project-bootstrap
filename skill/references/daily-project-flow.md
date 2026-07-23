# Daily GitHub project flow

## Goal

Translate ordinary descriptions into safe GitHub operations. The user should not need to remember Issue numbers, status-transition wording, or a long prompt.

## Intent shortcuts

| User intent | Default interpretation |
|---|---|
| `记一下：…` | Preserve an uncertain idea as a Project draft in Backlog when available. |
| `收需求：…` | Extract and deduplicate candidate Issues, then ask once for any creation not already authorized. |
| `开始做：…` | Find the best existing Issue, start it, implement it, validate it, and open a linked PR. |
| `收尾` | Inspect the current Issue/PR, record evidence, and prepare the gated next step. |
| `合并收尾` | Merge qualifying merge-ready PRs in the current repository, one at a time, without deploying or publishing. |
| `托管` | Supervise the current repository and current explicit goal, active Issue, or active PR. |
| `托管：…` | Supervise the supplied goal or scope and escalate only at human gates. |

Natural-language equivalents have the same meaning. These phrases are conveniences, not magic syntax.

For bare `托管`, do not ask the user to restate context that is already clear from the current repository, conversation, active Issue, or active PR. Ask one concise scope question only when several candidates remain plausible. Combine missing cadence and merge-policy choices into the same one-time setup question.

For continuous supervision, read [managed autopilot](managed-autopilot.md). Managed mode reuses this lifecycle and authorization matrix; it does not create a second workflow.

## Finding the Issue

Build a query from product area, outcome, distinctive nouns, labels, assignee, and recent activity. Prefer open Issues in `Ready`, `In progress`, or `Blocked`.

- One high-confidence result: use it and tell the user its number and title.
- Two or three plausible results: show a short shortlist and ask one question.
- No result: distinguish a clear new task from an uncertain idea. Create only when the current request or repository policy authorizes creation.

Do not ask the user to search GitHub or memorize a number when the agent can resolve it.

## Routine lifecycle

1. Read the Issue, acceptance criteria, dependencies, and current Project state.
2. Check whether a dependency or conflicting active branch blocks work.
3. Move `Ready` to `In progress` and create a dedicated branch.
4. Implement only the agreed scope and run repository validation. If an early PR is useful, keep it draft and leave the Issue `In progress`.
5. Link the PR to the Issue, report exact evidence, and mark the PR ready for formal review when implementation and scoped validation are complete enough to request a decision. If work is already complete when creating the PR, create it non-draft or mark it ready immediately. This project workflow overrides a generic publisher's draft-by-default convention. Make this transition without waiting for review or approval, including the final merge-gate result that formal review exists to collect.
6. Move the linked Issue to `In review` in the same handoff. `Ready for review` is a PR stage, never an Issue or Project status.
7. Let current-head CI and the repository-approved review signal provide merge-readiness evidence. An authorized observer or the single supervisor should repair a missed metadata transition without handing the task back to the implementer.
8. Return to implementation only for code, tests, conflicts, unresolved findings, or unmet acceptance criteria. Otherwise proceed to the integration gate.
9. Ask before merge or deployment unless the current request expressly authorized it.

## Separate review readiness from merge readiness

Use two independent decisions:

- **Review readiness** asks whether the scoped implementation, tests, migration notes, risks, and rollback evidence are complete enough for a reviewer to decide. When yes, exit Draft and move the Issue to `In review`.
- **Merge readiness** asks whether the current head has every required CI result, repository-approved review signal, resolved finding/thread, dependency, any externally required approval, and explicit merge authorization. Evaluate this only after formal review begins and again immediately before merge.

Draft is an implementation-stage signal, not a buffer for downstream review evidence. Never require a merge gate that rejects Draft PRs to pass before removing Draft. For high-risk work, the normal sequence is: complete implementation → exit Draft → obtain the repository-approved current-head review signal → settle findings → run the live merge gate → request or apply merge authorization. Require a non-author human `APPROVED` review only when repository policy or platform rules explicitly choose that model.

For a single accountable owner coordinating several Agents, a traceable current-head Agent review may be the repository-approved signal. It can be carried by a `COMMENTED` review, Bot review, structured PR comment, or same-owner GitHub identity when repository policy defines the marker and provenance. Treat it as evidence that review occurred, not as a human GitHub approval. Blocking findings, active change requests, and unresolved actionable threads still prevent merge.

The independent reviewer should publish that final signal as part of the same substantive review. Do not dispatch another approver-only Agent to restate the verdict or click `Approve`. A distinct non-author GitHub approval remains a separate external gate only when the repository ruleset, branch protection, or recorded policy explicitly requires that identity.

Before deciding what to do with a blocker, classify it:

| Blocker class | Examples | Required response |
|---|---|---|
| Implementation or acceptance defect | wrong behavior, missing test, unmet acceptance criterion | return to implementation |
| Evidence gap | CI pending, validation not recorded | collect or rerun evidence; do not call the code defective |
| Metadata lag | completed PR still Draft, Issue still `In progress` | reconcile state idempotently |
| External authorization | platform-required approval or merge authorization missing | enter/keep formal review and wait at that gate |
| Dependency or baseline change | another PR merged, base changed, conflict appeared | sync, resolve if needed, and rerun current-head evidence |

If a state transition is itself required to obtain the missing evidence, perform the transition instead of creating a circular blocker. A metadata-only correction never justifies handing work back to the implementer.

## Authorization matrix

| Action | Clearly selected task | Ambiguous or expanded work |
|---|---:|---:|
| Read/search GitHub | Automatic | Automatic |
| Change Ready to In progress | Automatic | Ask |
| Create task branch | Automatic | Ask |
| Open linked PR | Automatic | Ask |
| Mark PR ready, record tests, and move linked Issue to In review | Automatic | Ask |
| Create a clearly requested Issue | Allowed when repository policy says so | Ask once |
| Change scope or acceptance criteria | Ask | Ask |
| Close as Not planned, delete, publish, deploy | Ask | Ask |
| Merge | Ask unless this turn says `合并收尾` or otherwise authorizes merge | Ask |

The repository may impose stricter rules. A GitHub or execution tool may still request platform approval.

## Batch intake

For `收需求`, first normalize candidate items, search for duplicates, and classify them as existing Issue, clear new Issue, or uncertain idea. Present one compact table and consolidate all required approval into one question. Add clear work to Issues/Project; keep uncertain ideas as Project drafts where supported.

## Integrate merge-ready pull requests

Treat `合并收尾` and the expanded `/prompts:integrate` (Codex) or `/integrate` (Claude Code) shortcut as explicit merge authorization for the current turn only. Limit the operation to the current repository and any scope the user supplied.

1. Fetch current GitHub state; do not decide from a stale local snapshot.
2. Select open, non-draft PRs that have the repository-approved current-head review signal and any separately required platform approvals.
3. Order them by explicit dependencies, then by the repository's documented priority. Do not guess a dependency when order changes behavior.
4. Before each merge, verify that acceptance criteria are satisfied, required CI is current and successful, no merge conflict exists, and no unresolved review thread remains.
5. Respect branch protection and the repository's merge method. Never bypass a required check or a platform/repository approval that is actually configured.
6. Merge one PR, refresh GitHub state, then evaluate the next PR against the new base.
7. Skip any PR that no longer qualifies and record the exact reason. Stop the batch if a systemic failure makes later decisions unreliable.
8. Report merged and skipped PRs separately, including linked Issues and final checks.

This authorization does not include deployment, publishing, releases, tag deletion, scope expansion, or closing work as `Not planned`. Platform approval prompts still apply.
