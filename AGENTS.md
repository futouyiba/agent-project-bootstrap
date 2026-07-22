# Repository instructions

- Keep the installer compatible with macOS, Linux, and Windows PowerShell.
- Use only the Python standard library in scripts under `skill/scripts/`.
- Treat GitHub Issues/Projects as mutable task state; do not add a second editable task list.
- Preserve existing user files during installation. Back up an existing installed skill before replacing it.
- Validate changes with `python3 -m unittest discover -s tests -v` and the relevant platform installer test.
- Keep the public `skill/` directory installable as-is.
- Resolve ordinary task descriptions without requiring the user to know an Issue number.
- For clearly selected work, routine branch/PR/status updates are allowed; ask before scope changes, merge, deletion, publishing, or deployment unless the user explicitly invokes `合并收尾` for a merge-only integration turn or repository managed-mode policy authorizes a qualifying low-risk auto-merge.
- Treat `Ready for review` as PR state only. Keep draft work `In progress`, move the linked Issue to `In review` when the PR becomes ready for formal review, and never return work to an implementer solely for a metadata update.
- Draft is only for incomplete work or early feedback. Once implementation and scoped validation finish, create a non-draft PR or mark it ready before review; this overrides generic draft-by-default publishing behavior.
- Let the independent reviewer publish the final review signal in the same substantive review. Do not add an approver-only Agent unless repository or platform policy explicitly requires a distinct GitHub approval identity.
- Treat bare `托管` as a request to configure one bounded supervisor for the current repository and current explicit goal, active Issue, or active PR; ask only when scope is ambiguous. It never grants deployment, publishing, destructive changes, or unlimited merge authority.
- Keep GitHub Agentic Workflows opt-in and staged on first installation. Commit generated lock files, use only typed safe outputs for writes, and never give the event-driven integrator merge, deployment, publishing, secret, billing, deletion, destructive migration, or scope-expansion authority.
