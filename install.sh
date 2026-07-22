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
  package_root="${source_dir%/}"
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
  package_root="$temporary_dir/agent-project-bootstrap-$repository_ref"
fi

skill_source="$package_root/skill"
prompt_source="$package_root/prompts/integrate.md"

if [ ! -f "$skill_source/SKILL.md" ] || [ ! -f "$skill_source/agents/openai.yaml" ] || [ ! -f "$prompt_source" ]; then
  printf 'Invalid source: expected an installable skill at %s\n' "$skill_source" >&2
  exit 1
fi

skills_root="$codex_root/skills"
destination="$skills_root/agent-project-bootstrap"
mkdir -p "$skills_root"

if [ -e "$destination" ]; then
  backup="$destination.backup.$(date +%Y%m%d%H%M%S).$$"
  mv "$destination" "$backup"
  printf 'Existing installation backed up to %s\n' "$backup"
fi

cp -R "$skill_source" "$destination"
printf 'Installed agent-project-bootstrap to %s\n' "$destination"

prompts_root="$codex_root/prompts"
prompt_destination="$prompts_root/integrate.md"
mkdir -p "$prompts_root"
if [ -f "$prompt_destination" ] && ! cmp -s "$prompt_source" "$prompt_destination"; then
  prompt_backup="$prompt_destination.backup.$(date +%Y%m%d%H%M%S).$$"
  cp "$prompt_destination" "$prompt_backup"
  printf 'Existing integrate prompt backed up to %s\n' "$prompt_backup"
fi
cp "$prompt_source" "$prompt_destination"
printf 'Installed global /prompts:integrate shortcut to %s\n' "$prompt_destination"

if [ "$with_global_rule" -eq 1 ]; then
  agents_file="$codex_root/AGENTS.md"
  mkdir -p "$codex_root"
  touch "$agents_file"
  agents_temp="$(mktemp)"
  start_count="$(awk '{ count += gsub(/<!-- agent-project-bootstrap:start -->/, "&") } END { print count + 0 }' "$agents_file")"
  end_count="$(awk '{ count += gsub(/<!-- agent-project-bootstrap:end -->/, "&") } END { print count + 0 }' "$agents_file")"
  if [ "$start_count" -eq 1 ] && [ "$end_count" -eq 1 ]; then
    start_line="$(grep -n '<!-- agent-project-bootstrap:start -->' "$agents_file" | cut -d: -f1)"
    end_line="$(grep -n '<!-- agent-project-bootstrap:end -->' "$agents_file" | cut -d: -f1)"
    if [ "$start_line" -ge "$end_line" ]; then
      rm -f "$agents_temp"
      printf 'Refusing to update %s: managed block markers are out of order.\n' "$agents_file" >&2
      exit 1
    fi
    sed '/<!-- agent-project-bootstrap:start -->/,/<!-- agent-project-bootstrap:end -->/d' "$agents_file" >"$agents_temp"
  elif [ "$start_count" -eq 0 ] && [ "$end_count" -eq 0 ]; then
    cp "$agents_file" "$agents_temp"
  else
    rm -f "$agents_temp"
    printf 'Refusing to update %s: managed block markers are incomplete or duplicated.\n' "$agents_file" >&2
    exit 1
  fi
  cat >>"$agents_temp" <<'EOF'

<!-- agent-project-bootstrap:start -->
## Agent Project Workflow

- On the first substantive request that may modify a Git repository, check for `.codex/agent-project-bootstrap.yml` or equivalent project coordination.
- If neither exists, use `agent-project-bootstrap` for a read-only audit and offer a concise interactive initialization.
- Do not create bootstrap files until the user authorizes the proposed scope.
- Accept natural-language task descriptions and never require the user to know an Issue number. Resolve one clear match, shortlist ambiguous matches, and propose or create missing work according to repository policy.
- Treat `记一下`, `收需求`, `开始做`, `收尾`, `合并收尾`, and `托管` as shortcuts for the `agent-project-bootstrap` flow. Bare `托管` means the current repository and current explicit goal, active Issue, or active PR; ask only when that scope is ambiguous.
- Treat an explicit `合并收尾` request or the expanded `/prompts:integrate` prompt as merge authorization for that turn only. Merge only qualifying PRs in the current repository; never deploy or publish.
- When repository policy enables managed mode, use one durable supervisor to refresh GitHub on each scheduled wake-up and continue routine review/CI handoffs without asking the user to relay messages. Automatic merge still requires the repository's explicit standing policy.
- Keep repository-specific Project URLs, status names, test commands, and standing authorization in the repository `AGENTS.md`; repository rules take precedence.
- Global guidance alone never authorizes scope changes, deletion, merge, publishing, or deployment.
<!-- agent-project-bootstrap:end -->
EOF
  cp "$agents_temp" "$agents_file"
  rm -f "$agents_temp"
  printf 'Added or updated the optional global project-workflow rule in %s\n' "$agents_file"
fi

printf '%s\n' "Restart ChatGPT/Codex if the skill does not appear immediately."
printf '%s\n' "Invoke with @agent-project-bootstrap in ChatGPT or \$agent-project-bootstrap in Codex."
printf '%s\n' "In Codex CLI/IDE, use /prompts:integrate for the deprecated custom-prompt shortcut."
