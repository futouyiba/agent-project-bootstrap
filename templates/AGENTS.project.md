# Project coordination

## Source of truth

- Use GitHub Issues and this repository's Project as mutable task state. Do not maintain a second editable task table.
- Record the Project URL and exact statuses here: `Backlog`, `Ready`, `In progress`, `Blocked`, `In review`, `Done`.
- Treat `.codex/cache/github-snapshot.json` as a disposable read-only cache, never as task state.

## Natural-language intake

- The user does not need to know an Issue number. Search the fresh local snapshot and GitHub from their description.
- For one clear match, select it and report its number. For several plausible matches, show the best two or three and ask one question.
- Treat `记一下`, `收需求`, `开始做`, and `收尾` as workflow shortcuts described by `agent-project-bootstrap`.

## Standing authorization

- For a clearly selected task, the agent may read GitHub state, move `Ready` to `In progress`, create a task branch, open and link a PR, move to `In review`, and record validation results.
- Ask before creating work not clearly implied by the conversation, changing scope or acceptance criteria, closing as `Not planned`, deleting records, merging, publishing, or deploying.
- Platform approval prompts still apply. A direct user request can grant narrower or broader authorization for that request.

## Delivery

- Read the Issue, acceptance criteria, and dependencies before changing code.
- Do not expand scope silently; propose a follow-up Issue.
- Use a dedicated branch and pull request for each independently deliverable Issue.
- Run the repository's documented validation commands and report exact results.
- Do not merge while required checks fail or without the required approval.
