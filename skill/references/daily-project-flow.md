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
| `合并收尾` | Merge qualifying approved PRs in the current repository, one at a time, without deploying or publishing. |

Natural-language equivalents have the same meaning. These phrases are conveniences, not magic syntax.

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
4. Implement only the agreed scope and run repository validation.
5. Open a PR that links the Issue and reports exact evidence.
6. Move the item to `In review`.
7. Let CI and review provide merge-readiness evidence.
8. Ask before merge or deployment unless the current request expressly authorized it.

## Authorization matrix

| Action | Clearly selected task | Ambiguous or expanded work |
|---|---:|---:|
| Read/search GitHub | Automatic | Automatic |
| Change Ready to In progress | Automatic | Ask |
| Create task branch | Automatic | Ask |
| Open linked PR | Automatic | Ask |
| Record tests and move to In review | Automatic | Ask |
| Create a clearly requested Issue | Allowed when repository policy says so | Ask once |
| Change scope or acceptance criteria | Ask | Ask |
| Close as Not planned, delete, publish, deploy | Ask | Ask |
| Merge | Ask unless this turn says `合并收尾` or otherwise authorizes merge | Ask |

The repository may impose stricter rules. A GitHub or execution tool may still request platform approval.

## Batch intake

For `收需求`, first normalize candidate items, search for duplicates, and classify them as existing Issue, clear new Issue, or uncertain idea. Present one compact table and consolidate all required approval into one question. Add clear work to Issues/Project; keep uncertain ideas as Project drafts where supported.

## Integrate approved pull requests

Treat `合并收尾` and the expanded global `/prompts:integrate` prompt as explicit merge authorization for the current turn only. Limit the operation to the current repository and any scope the user supplied.

1. Fetch current GitHub state; do not decide from a stale local snapshot.
2. Select open, non-draft PRs that have all required approvals.
3. Order them by explicit dependencies, then by the repository's documented priority. Do not guess a dependency when order changes behavior.
4. Before each merge, verify that acceptance criteria are satisfied, required CI is current and successful, no merge conflict exists, and no unresolved review thread remains.
5. Respect branch protection and the repository's merge method. Never bypass a required check or approval.
6. Merge one PR, refresh GitHub state, then evaluate the next PR against the new base.
7. Skip any PR that no longer qualifies and record the exact reason. Stop the batch if a systemic failure makes later decisions unreliable.
8. Report merged and skipped PRs separately, including linked Issues and final checks.

This authorization does not include deployment, publishing, releases, tag deletion, scope expansion, or closing work as `Not planned`. Platform approval prompts still apply.
