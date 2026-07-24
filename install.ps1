param(
    [switch]$WithGlobalRule,
    [string]$Source,
    [string]$CodexHome,
    [string]$ClaudeHome,
    [string]$Target = "codex"
)

$ErrorActionPreference = "Stop"
$RepositorySlug = "futouyiba/agent-project-bootstrap"
$RepositoryRef = "main"
$TemporaryDirectory = $null
$InstallStaging = $null

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        $CodexRoot = $env:CODEX_HOME
    } else {
        $CodexRoot = Join-Path $HOME ".codex"
    }
} else {
    $CodexRoot = $CodexHome
}

if ([string]::IsNullOrWhiteSpace($ClaudeHome)) {
    if (-not [string]::IsNullOrWhiteSpace($env:CLAUDE_CONFIG_DIR)) {
        $ClaudeRoot = $env:CLAUDE_CONFIG_DIR
    } else {
        $ClaudeRoot = Join-Path $HOME ".claude"
    }
} else {
    $ClaudeRoot = $ClaudeHome
}

switch ($Target) {
    "codex" {
        $InstallRoot = $CodexRoot
        $CommandDirName = "prompts"
        $CommandSourceRelative = "prompts/integrate.md"
        $GlobalRulesFile = "AGENTS.md"
        $IntegrateCommand = "/prompts:integrate"
        $RepoRulesFile = "AGENTS.md"
    }
    "claude" {
        $InstallRoot = $ClaudeRoot
        $CommandDirName = "commands"
        $CommandSourceRelative = "commands/integrate.md"
        $GlobalRulesFile = "CLAUDE.md"
        $IntegrateCommand = "/integrate"
        $RepoRulesFile = "CLAUDE.md"
    }
    default {
        throw "Unknown target: $Target (expected codex or claude)"
    }
}

try {
    if (-not [string]::IsNullOrWhiteSpace($Source)) {
        $PackageRoot = Resolve-Path $Source
    } else {
        $TemporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-project-bootstrap-" + [guid]::NewGuid())
        New-Item -ItemType Directory -Path $TemporaryDirectory | Out-Null
        $ArchivePath = Join-Path $TemporaryDirectory "source.zip"
        $ArchiveUrl = "https://github.com/$RepositorySlug/archive/refs/heads/$RepositoryRef.zip"
        Invoke-WebRequest -Uri $ArchiveUrl -OutFile $ArchivePath
        Expand-Archive -Path $ArchivePath -DestinationPath $TemporaryDirectory
        $PackageRoot = Join-Path $TemporaryDirectory "agent-project-bootstrap-$RepositoryRef"
    }

    $BootstrapSkillSource = Join-Path $PackageRoot "skill"
    $IssueLoopSkillSource = Join-Path $PackageRoot "skills/agent-issue-loop"
    $PrLoopSkillSource = Join-Path $PackageRoot "skills/agent-pr-loop"
    $CommandSource = Join-Path $PackageRoot $CommandSourceRelative

    if (-not (Test-Path (Join-Path $BootstrapSkillSource "SKILL.md")) -or
        -not (Test-Path (Join-Path $IssueLoopSkillSource "SKILL.md")) -or
        -not (Test-Path (Join-Path $PrLoopSkillSource "SKILL.md")) -or
        -not (Test-Path $CommandSource)) {
        throw "Invalid source: expected installable Skills at $BootstrapSkillSource, $IssueLoopSkillSource, and $PrLoopSkillSource"
    }
    if ($Target -eq "codex" -and
        (-not (Test-Path (Join-Path $BootstrapSkillSource "agents/openai.yaml")) -or
         -not (Test-Path (Join-Path $IssueLoopSkillSource "agents/openai.yaml")) -or
         -not (Test-Path (Join-Path $PrLoopSkillSource "agents/openai.yaml")))) {
        throw "Invalid source: codex target requires agents/openai.yaml in all Skills"
    }

    $SkillsRoot = Join-Path $InstallRoot "skills"
    New-Item -ItemType Directory -Force -Path $SkillsRoot | Out-Null
    $InstallStaging = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-project-skills-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $InstallStaging | Out-Null
    Copy-Item -Recurse -Path $BootstrapSkillSource -Destination (Join-Path $InstallStaging "agent-project-bootstrap")
    Copy-Item -Recurse -Path $IssueLoopSkillSource -Destination (Join-Path $InstallStaging "agent-issue-loop")
    Copy-Item -Recurse -Path $PrLoopSkillSource -Destination (Join-Path $InstallStaging "agent-pr-loop")

    foreach ($SkillName in @("agent-project-bootstrap", "agent-issue-loop", "agent-pr-loop")) {
        $Destination = Join-Path $SkillsRoot $SkillName
        if (Test-Path $Destination) {
            $Timestamp = Get-Date -Format "yyyyMMddHHmmss"
            $BackupSuffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
            $Backup = "$Destination.backup.$Timestamp.$BackupSuffix"
            Move-Item -Path $Destination -Destination $Backup
            Write-Host "Existing installation backed up to $Backup"
        }
        Move-Item -Path (Join-Path $InstallStaging $SkillName) -Destination $Destination
        if (-not (Test-Path (Join-Path $Destination "SKILL.md"))) {
            throw "Installed Skill failed readback verification: $Destination"
        }
        Write-Host "Installed $SkillName to $Destination"
    }
    Remove-Item -Recurse -Force $InstallStaging

    $CommandRoot = Join-Path $InstallRoot $CommandDirName
    $CommandDestination = Join-Path $CommandRoot "integrate.md"
    New-Item -ItemType Directory -Force -Path $CommandRoot | Out-Null
    if (Test-Path $CommandDestination) {
        $SourceHash = (Get-FileHash -Algorithm SHA256 -Path $CommandSource).Hash
        $DestinationHash = (Get-FileHash -Algorithm SHA256 -Path $CommandDestination).Hash
        if ($SourceHash -ne $DestinationHash) {
            $CommandTimestamp = Get-Date -Format "yyyyMMddHHmmss"
            $CommandBackupSuffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
            $CommandBackup = "$CommandDestination.backup.$CommandTimestamp.$CommandBackupSuffix"
            Copy-Item -Path $CommandDestination -Destination $CommandBackup
            Write-Host "Existing $IntegrateCommand shortcut backed up to $CommandBackup"
        }
    }
    Copy-Item -Force -Path $CommandSource -Destination $CommandDestination
    Write-Host "Installed global $IntegrateCommand shortcut to $CommandDestination"

    if ($WithGlobalRule) {
        New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
        $RulesFile = Join-Path $InstallRoot $GlobalRulesFile
        if (-not (Test-Path $RulesFile)) {
            New-Item -ItemType File -Path $RulesFile | Out-Null
        }
        $Existing = if ((Get-Item $RulesFile).Length -gt 0) {
            Get-Content -Raw -Path $RulesFile
        } else {
            ""
        }
        $Rule = @'

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
'@
        $Rule = $Rule -replace '__INTEGRATE_COMMAND__', $IntegrateCommand -replace '__REPO_RULES_FILE__', $RepoRulesFile
        $StartMarker = "<!-- agent-project-bootstrap:start -->"
        $EndMarker = "<!-- agent-project-bootstrap:end -->"
        $StartCount = [regex]::Matches($Existing, [regex]::Escape($StartMarker)).Count
        $EndCount = [regex]::Matches($Existing, [regex]::Escape($EndMarker)).Count
        if ($StartCount -eq 1 -and $EndCount -eq 1 -and $Existing.IndexOf($StartMarker) -lt $Existing.IndexOf($EndMarker)) {
            $StandaloneStartPattern = '(?m)^[\t ]*' + [regex]::Escape($StartMarker) + '[\t ]*\r?$'
            $StandaloneEndPattern = '(?m)^[\t ]*' + [regex]::Escape($EndMarker) + '[\t ]*\r?$'
            if (-not [regex]::IsMatch($Existing, $StandaloneStartPattern) -or
                -not [regex]::IsMatch($Existing, $StandaloneEndPattern)) {
                throw "Refusing to update $RulesFile because managed block markers must be on their own lines."
            }
            $Pattern = '(?s)<!-- agent-project-bootstrap:start -->.*?<!-- agent-project-bootstrap:end -->'
            $WithoutOldRule = [regex]::Replace($Existing, $Pattern, "").TrimEnd()
        } elseif ($StartCount -eq 0 -and $EndCount -eq 0) {
            $WithoutOldRule = $Existing.TrimEnd()
        } else {
            throw "Refusing to update $RulesFile because managed block markers are incomplete, duplicated, or out of order."
        }
        if ([string]::IsNullOrWhiteSpace($WithoutOldRule)) {
            $Updated = $Rule.TrimStart()
        } else {
            $Updated = $WithoutOldRule + [Environment]::NewLine + $Rule
        }
        Set-Content -Path $RulesFile -Value $Updated -Encoding utf8
        Write-Host "Added or updated the optional global project-workflow rule in $RulesFile"
    }

    if ($Target -eq "claude") {
        Write-Host "Restart Claude Code if the skill does not appear immediately."
        Write-Host "In Claude Code the three Skills are available automatically; describe the Issue or PR directly, or run /integrate to merge approved PRs."
    } else {
        Write-Host "Restart ChatGPT/Codex if the skill does not appear immediately."
        Write-Host 'Invoke with @agent-project-bootstrap in ChatGPT or $agent-project-bootstrap, $agent-issue-loop, and $agent-pr-loop in Codex.'
        Write-Host 'In Codex CLI/IDE, use /prompts:integrate for the deprecated custom-prompt shortcut.'
    }
}
finally {
    if ($null -ne $InstallStaging -and (Test-Path $InstallStaging)) {
        Remove-Item -Recurse -Force $InstallStaging
    }
    if ($null -ne $TemporaryDirectory -and (Test-Path $TemporaryDirectory)) {
        Remove-Item -Recurse -Force $TemporaryDirectory
    }
}
