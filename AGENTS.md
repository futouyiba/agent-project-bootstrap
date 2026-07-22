# Repository instructions

- Keep the installer compatible with macOS, Linux, and Windows PowerShell.
- Use only the Python standard library in scripts under `skill/scripts/`.
- Treat GitHub Issues/Projects as mutable task state; do not add a second editable task list.
- Preserve existing user files during installation. Back up an existing installed skill before replacing it.
- Validate changes with `python3 -m unittest discover -s tests -v` and the relevant platform installer test.
- Keep the public `skill/` directory installable as-is.
- Resolve ordinary task descriptions without requiring the user to know an Issue number.
- For clearly selected work, routine branch/PR/status updates are allowed; ask before scope changes, merge, deletion, publishing, or deployment unless the user explicitly invokes `合并收尾` for a merge-only integration turn.
