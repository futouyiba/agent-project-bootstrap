#!/bin/sh
set -eu

repository_slug="futouyiba/agent-project-bootstrap"
repository_ref="main"
source_dir=""
codex_root="${CODEX_HOME:-${HOME}/.codex}"
with_global_rule=0
temporary_dir=""

usage() {
  printf '%s\n' "Usage: install.sh [--source PATH] [--codex-home PATH] [--with-global-rule]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source)
      source_dir="${2:?--source requires a path}"
      shift 2
      ;;
    --codex-home)
      codex_root="${2:?--codex-home requires a path}"
      shift 2
      ;;
    --with-global-rule)
      with_global_rule=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cleanup() {
  if [ -n "$temporary_dir" ] && [ -d "$temporary_dir" ]; then
    rm -rf "$temporary_dir"
  fi
}
trap cleanup EXIT HUP INT TERM

if [ -n "$source_dir" ]; then
  skill_source="${source_dir%/}/skill"
else
  command -v curl >/dev/null 2>&1 || {
    printf '%s\n' "curl is required for remote installation." >&2
    exit 1
  }
  command -v tar >/dev/null 2>&1 || {
    printf '%s\n' "tar is required for remote installation." >&2
    exit 1
  }
  temporary_dir="$(mktemp -d)"
  archive_path="$temporary_dir/source.tar.gz"
  curl -fsSL "https://github.com/$repository_slug/archive/refs/heads/$repository_ref.tar.gz" -o "$archive_path"
  tar -xzf "$archive_path" -C "$temporary_dir"
  skill_source="$temporary_dir/agent-project-bootstrap-$repository_ref/skill"
fi

if [ ! -f "$skill_source/SKILL.md" ] || [ ! -f "$skill_source/agents/openai.yaml" ]; then
  printf 'Invalid source: expected an installable skill at %s\n' "$skill_source" >&2
  exit 1
fi

skills_root="$codex_root/skills"
destination="$skills_root/agent-project-bootstrap"
mkdir -p "$skills_root"

if [ -e "$destination" ]; then
  backup="$destination.backup.$(date +%Y%m%d%H%M%S)"
  mv "$destination" "$backup"
  printf 'Existing installation backed up to %s\n' "$backup"
fi

cp -R "$skill_source" "$destination"
printf 'Installed agent-project-bootstrap to %s\n' "$destination"

if [ "$with_global_rule" -eq 1 ]; then
  agents_file="$codex_root/AGENTS.md"
  mkdir -p "$codex_root"
  touch "$agents_file"
  if grep -q '<!-- agent-project-bootstrap:start -->' "$agents_file"; then
    printf 'Global bootstrap rule already exists in %s\n' "$agents_file"
  else
    cat >>"$agents_file" <<'EOF'

<!-- agent-project-bootstrap:start -->
## Agent Project Bootstrap

- On the first substantive request that may modify a Git repository, check for `.codex/agent-project-bootstrap.yml` or equivalent project coordination.
- If neither exists, use `agent-project-bootstrap` for a read-only audit and offer a concise interactive initialization.
- Do not create bootstrap files until the user authorizes the proposed scope.
- Prefer GitHub Issues/Projects for mutable task state, repository `AGENTS.md` for stable policy, pull requests for delivery, and CI for merge gates.
<!-- agent-project-bootstrap:end -->
EOF
    printf 'Added the optional global bootstrap rule to %s\n' "$agents_file"
  fi
fi

printf '%s\n' "Restart ChatGPT/Codex if the skill does not appear immediately."
printf '%s\n' "Invoke with @agent-project-bootstrap in ChatGPT or \$agent-project-bootstrap in Codex."

