#!/bin/sh
set -eu

repository_slug="futouyiba/agent-project-bootstrap"
repository_ref="main"
source_dir=""
codex_root="${CODEX_HOME:-${HOME}/.codex}"
claude_root="${CLAUDE_CONFIG_DIR:-${HOME}/.claude}"
target="codex"
with_global_rule=0
temporary_dir=""
install_staging=""

usage() {
  printf '%s\n' "Usage: install.sh [--source PATH] [--target codex|claude] [--codex-home PATH] [--claude-home PATH] [--with-global-rule]"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --source)
      source_dir="${2:?--source requires a path}"
      shift 2
      ;;
    --target)
      target="${2:?--target requires codex or claude}"
      shift 2
      ;;
    --codex-home)
      codex_root="${2:?--codex-home requires a path}"
      shift 2
      ;;
    --claude-home)
      claude_root="${2:?--claude-home requires a path}"
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

case "$target" in
  codex)
    install_root="$codex_root"
    command_dir_name="prompts"
    command_source_relative="prompts/integrate.md"
    global_rules_file="AGENTS.md"
    integrate_command="/prompts:integrate"
    repo_rules_file="AGENTS.md"
    ;;
  claude)
    install_root="$claude_root"
    command_dir_name="commands"
    command_source_relative="commands/integrate.md"
    global_rules_file="CLAUDE.md"
    integrate_command="/integrate"
    repo_rules_file="CLAUDE.md"
    ;;
  *)
    printf 'Unknown target: %s (expected codex or claude)\n' "$target" >&2
    exit 2
    ;;
esac

cleanup() {
  if [ -n "$temporary_dir" ] && [ -d "$temporary_dir" ]; then
    rm -rf "$temporary_dir"
  fi
  if [ -n "$install_staging" ] && [ -d "$install_staging" ]; then
    rm -rf "$install_staging"
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

bootstrap_skill_source="$package_root/skill"
issue_loop_skill_source="$package_root/skills/agent-issue-loop"
pr_loop_skill_source="$package_root/skills/agent-pr-loop"
command_source="$package_root/$command_source_relative"

# Validate every source before replacing any installed Skill.
if [ ! -f "$bootstrap_skill_source/SKILL.md" ] || [ ! -f "$issue_loop_skill_source/SKILL.md" ] ||
  [ ! -f "$pr_loop_skill_source/SKILL.md" ] ||
  [ ! -f "$command_source" ]; then
  printf 'Invalid source: expected installable Skills at %s, %s, and %s\n' \
    "$bootstrap_skill_source" "$issue_loop_skill_source" "$pr_loop_skill_source" >&2
  exit 1
fi
if [ "$target" = "codex" ] &&
  { [ ! -f "$bootstrap_skill_source/agents/openai.yaml" ] ||
    [ ! -f "$issue_loop_skill_source/agents/openai.yaml" ] ||
    [ ! -f "$pr_loop_skill_source/agents/openai.yaml" ]; }; then
  printf 'Invalid source: codex target requires agents/openai.yaml in all Skills\n' >&2
  exit 1
fi

skills_root="$install_root/skills"
mkdir -p "$skills_root"
install_staging="$(mktemp -d)"
cp -R "$bootstrap_skill_source" "$install_staging/agent-project-bootstrap"
cp -R "$issue_loop_skill_source" "$install_staging/agent-issue-loop"
cp -R "$pr_loop_skill_source" "$install_staging/agent-pr-loop"

for skill_name in agent-project-bootstrap agent-issue-loop agent-pr-loop; do
  destination="$skills_root/$skill_name"
  if [ -e "$destination" ]; then
    backup="$destination.backup.$(date +%Y%m%d%H%M%S).$$"
    mv "$destination" "$backup"
    printf 'Existing installation backed up to %s\n' "$backup"
  fi
  mv "$install_staging/$skill_name" "$destination"
  test -f "$destination/SKILL.md"
  printf 'Installed %s to %s\n' "$skill_name" "$destination"
done

command_root="$install_root/$command_dir_name"
command_destination="$command_root/integrate.md"
mkdir -p "$command_root"
if [ -f "$command_destination" ] && ! cmp -s "$command_source" "$command_destination"; then
  command_backup="$command_destination.backup.$(date +%Y%m%d%H%M%S).$$"
  cp "$command_destination" "$command_backup"
  printf 'Existing %s shortcut backed up to %s\n' "$integrate_command" "$command_backup"
fi
cp "$command_source" "$command_destination"
printf 'Installed global %s shortcut to %s\n' "$integrate_command" "$command_destination"

if [ "$with_global_rule" -eq 1 ]; then
  rules_file="$install_root/$global_rules_file"
  mkdir -p "$install_root"
  touch "$rules_file"
  rules_temp="$(mktemp)"
  start_count="$(awk '{ count += gsub(/<!-- agent-project-bootstrap:start -->/, "&") } END { print count + 0 }' "$rules_file")"
  end_count="$(awk '{ count += gsub(/<!-- agent-project-bootstrap:end -->/, "&") } END { print count + 0 }' "$rules_file")"
  if [ "$start_count" -eq 1 ] && [ "$end_count" -eq 1 ]; then
    if ! grep -q '^[[:space:]]*<!-- agent-project-bootstrap:start -->[[:space:]]*$' "$rules_file" ||
      ! grep -q '^[[:space:]]*<!-- agent-project-bootstrap:end -->[[:space:]]*$' "$rules_file"; then
      rm -f "$rules_temp"
      printf 'Refusing to update %s: managed block markers must be on their own lines.\n' "$rules_file" >&2
      exit 1
    fi
    start_line="$(grep -n '<!-- agent-project-bootstrap:start -->' "$rules_file" | cut -d: -f1)"
    end_line="$(grep -n '<!-- agent-project-bootstrap:end -->' "$rules_file" | cut -d: -f1)"
    if [ "$start_line" -ge "$end_line" ]; then
      rm -f "$rules_temp"
      printf 'Refusing to update %s: managed block markers are out of order.\n' "$rules_file" >&2
      exit 1
    fi
    sed '/<!-- agent-project-bootstrap:start -->/,/<!-- agent-project-bootstrap:end -->/d' "$rules_file" >"$rules_temp"
  elif [ "$start_count" -eq 0 ] && [ "$end_count" -eq 0 ]; then
    cp "$rules_file" "$rules_temp"
  else
    rm -f "$rules_temp"
    printf 'Refusing to update %s: managed block markers are incomplete or duplicated.\n' "$rules_file" >&2
    exit 1
  fi
  block_rendered="$(mktemp)"
  cat >"$block_rendered" <<'EOF'

<!-- agent-project-bootstrap:start -->
## Agent Project Workflow

- On the first substantive request that may modify a Git repository, check for `.codex/agent-project-bootstrap.yml` or equivalent project coordination.
- If neither exists, use `agent-project-bootstrap` for a read-only audit and offer a concise interactive initialization.
- Do not create bootstrap files until the user authorizes the proposed scope.
- Accept natural-language task descriptions and never require the user to know an Issue number. Resolve one clear match, shortlist ambiguous matches, and propose or create missing work according to repository policy.
- Treat `记一下`, `收需求`, `开始做`, `收尾`, `合并收尾`, and `托管` as shortcuts for the `agent-project-bootstrap` flow. Bare `托管` means the current repository and current explicit goal, active Issue, or active PR; ask only when that scope is ambiguous.
- Treat `开始做这个Issue`, `解决这个Issue`, `搞定Issue`, `把当前Issue跑完`, explicit `agent-issue-loop`, or natural equivalents as invocation of the installed `agent-issue-loop` Skill. Keep one main coordinator through readiness, implementation, PR handoff, verified merge, and normal Issue closure; delegate its single PR to `agent-pr-loop`.
- Treat `搞定PR`, `搞定这个PR`, `搞定当前PR`, explicit `agent-pr-loop`, or natural equivalents as invocation of the installed `agent-pr-loop` Skill. For one selected PR, complete the comments/review/fix/current-head-CI loop and automatically merge when every gate passes; pause only at recorded human gates or an explicit no-merge instruction.
- In a single-owner repository where Agents share one GitHub account, use a current-head substantive COMMENT review as Agent-review evidence. Do not wait for or manufacture self-approval unless repository or platform policy requires another identity.
- Treat an explicit `合并收尾` request or the expanded `__INTEGRATE_COMMAND__` prompt as merge authorization for that generic integration turn only. For one PR delegated to `agent-pr-loop`, use its exact-head automatic-merge policy instead. Never deploy or publish.
- When repository policy enables managed mode, use one durable supervisor to refresh GitHub on each scheduled wake-up and continue routine review/CI handoffs without asking the user to relay messages. Automatic merge still requires the repository's explicit standing policy.
- When the user requests true GitHub event-driven handoffs, use the Skill's GitHub Agentic Workflows profile. It is repository-scoped, opt-in, and staged on first installation; the global rule never enables workflows, secrets, live writes, or merge.
- Keep repository-specific Project URLs, status names, test commands, and standing authorization in the repository `__REPO_RULES_FILE__`; repository rules take precedence.
- Outside the bounded `agent-issue-loop` and `agent-pr-loop` completion paths, global guidance alone never authorizes scope changes, deletion, merge, publishing, or deployment.
<!-- agent-project-bootstrap:end -->
EOF
  sed -e "s|__INTEGRATE_COMMAND__|$integrate_command|g" -e "s|__REPO_RULES_FILE__|$repo_rules_file|g" "$block_rendered" >>"$rules_temp"
  rm -f "$block_rendered"
  cp "$rules_temp" "$rules_file"
  rm -f "$rules_temp"
  printf 'Added or updated the optional global project-workflow rule in %s\n' "$rules_file"
fi

if [ "$target" = "claude" ]; then
  printf '%s\n' "Restart Claude Code if the skill does not appear immediately."
  printf '%s\n' "In Claude Code the three Skills are available automatically; describe the Issue or PR directly, or run /integrate to merge approved PRs."
else
  printf '%s\n' "Restart ChatGPT/Codex if the skill does not appear immediately."
  printf '%s\n' "Invoke with @agent-project-bootstrap in ChatGPT or \$agent-project-bootstrap, \$agent-issue-loop, and \$agent-pr-loop in Codex."
  printf '%s\n' "In Codex CLI/IDE, use /prompts:integrate for the deprecated custom-prompt shortcut."
fi
