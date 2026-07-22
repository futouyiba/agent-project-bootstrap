param(
    [switch]$WithGlobalRule,
    [string]$Source,
    [string]$CodexHome
)

$ErrorActionPreference = "Stop"
$RepositorySlug = "futouyiba/agent-project-bootstrap"
$RepositoryRef = "main"
$TemporaryDirectory = $null

if ([string]::IsNullOrWhiteSpace($CodexHome)) {
    if (-not [string]::IsNullOrWhiteSpace($env:CODEX_HOME)) {
        $CodexRoot = $env:CODEX_HOME
    } else {
        $CodexRoot = Join-Path $HOME ".codex"
    }
} else {
    $CodexRoot = $CodexHome
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

    $SkillSource = Join-Path $PackageRoot "skill"
    $PromptSource = Join-Path (Join-Path $PackageRoot "prompts") "integrate.md"

    if (-not (Test-Path (Join-Path $SkillSource "SKILL.md")) -or
        -not (Test-Path (Join-Path $SkillSource "agents/openai.yaml")) -or
        -not (Test-Path $PromptSource)) {
        throw "Invalid source: expected an installable skill at $SkillSource"
    }

    $SkillsRoot = Join-Path $CodexRoot "skills"
    $Destination = Join-Path $SkillsRoot "agent-project-bootstrap"
    New-Item -ItemType Directory -Force -Path $SkillsRoot | Out-Null

    if (Test-Path $Destination) {
        $Timestamp = Get-Date -Format "yyyyMMddHHmmss"
        $BackupSuffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
        $Backup = "$Destination.backup.$Timestamp.$BackupSuffix"
        Move-Item -Path $Destination -Destination $Backup
        Write-Host "Existing installation backed up to $Backup"
    }

    Copy-Item -Recurse -Path $SkillSource -Destination $Destination
    Write-Host "Installed agent-project-bootstrap to $Destination"

    $PromptsRoot = Join-Path $CodexRoot "prompts"
    $PromptDestination = Join-Path $PromptsRoot "integrate.md"
    New-Item -ItemType Directory -Force -Path $PromptsRoot | Out-Null
    if (Test-Path $PromptDestination) {
        $SourceHash = (Get-FileHash -Algorithm SHA256 -Path $PromptSource).Hash
        $DestinationHash = (Get-FileHash -Algorithm SHA256 -Path $PromptDestination).Hash
        if ($SourceHash -ne $DestinationHash) {
            $PromptTimestamp = Get-Date -Format "yyyyMMddHHmmss"
            $PromptBackupSuffix = [guid]::NewGuid().ToString("N").Substring(0, 8)
            $PromptBackup = "$PromptDestination.backup.$PromptTimestamp.$PromptBackupSuffix"
            Copy-Item -Path $PromptDestination -Destination $PromptBackup
            Write-Host "Existing integrate prompt backed up to $PromptBackup"
        }
    }
    Copy-Item -Force -Path $PromptSource -Destination $PromptDestination
    Write-Host "Installed global /prompts:integrate shortcut to $PromptDestination"

    if ($WithGlobalRule) {
        New-Item -ItemType Directory -Force -Path $CodexRoot | Out-Null
        $AgentsFile = Join-Path $CodexRoot "AGENTS.md"
        if (-not (Test-Path $AgentsFile)) {
            New-Item -ItemType File -Path $AgentsFile | Out-Null
        }
        $Existing = if ((Get-Item $AgentsFile).Length -gt 0) {
            Get-Content -Raw -Path $AgentsFile
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
- Treat an explicit `合并收尾` request or the expanded `/prompts:integrate` prompt as merge authorization for that turn only. Merge only qualifying PRs in the current repository; never deploy or publish.
- Keep artifact states distinct: `Ready for review` is a pull-request stage only, draft PR work remains `In progress`, and the linked Issue moves to `In review` when the PR becomes ready for formal review.
- Draft is only for incomplete work or early feedback. Once implementation and scoped validation are complete, create a non-draft PR or mark it ready immediately without waiting for review or approval; this workflow overrides generic draft-by-default publishing behavior.
- The independent reviewer that performs the substantive review should publish the final review signal. Do not create an approver-only Agent unless repository or platform policy explicitly requires a distinct GitHub approval identity.
- Let the first authorized observer or the repository's single supervisor reconcile routine metadata idempotently. Never send work back to the implementer solely to edit status; return it only for code, tests, conflicts, review findings, or unmet acceptance criteria.
- When repository policy enables managed mode, use one durable supervisor to refresh GitHub on each scheduled wake-up and continue routine review/CI handoffs without asking the user to relay messages. Automatic merge still requires the repository's explicit standing policy.
- When the user requests true GitHub event-driven handoffs, use the Skill's GitHub Agentic Workflows profile. It is repository-scoped, opt-in, and staged on first installation; the global rule never enables workflows, secrets, live writes, or merge.
- Keep repository-specific Project URLs, status names, test commands, and standing authorization in the repository `AGENTS.md`; repository rules take precedence.
- Global guidance alone never authorizes scope changes, deletion, merge, publishing, or deployment.
<!-- agent-project-bootstrap:end -->
'@
        $StartMarker = "<!-- agent-project-bootstrap:start -->"
        $EndMarker = "<!-- agent-project-bootstrap:end -->"
        $StartCount = [regex]::Matches($Existing, [regex]::Escape($StartMarker)).Count
        $EndCount = [regex]::Matches($Existing, [regex]::Escape($EndMarker)).Count
        if ($StartCount -eq 1 -and $EndCount -eq 1 -and $Existing.IndexOf($StartMarker) -lt $Existing.IndexOf($EndMarker)) {
            $StandaloneStartPattern = '(?m)^[\t ]*' + [regex]::Escape($StartMarker) + '[\t ]*\r?$'
            $StandaloneEndPattern = '(?m)^[\t ]*' + [regex]::Escape($EndMarker) + '[\t ]*\r?$'
            if (-not [regex]::IsMatch($Existing, $StandaloneStartPattern) -or
                -not [regex]::IsMatch($Existing, $StandaloneEndPattern)) {
                throw "Refusing to update $AgentsFile because managed block markers must be on their own lines."
            }
            $Pattern = '(?s)<!-- agent-project-bootstrap:start -->.*?<!-- agent-project-bootstrap:end -->'
            $WithoutOldRule = [regex]::Replace($Existing, $Pattern, "").TrimEnd()
        } elseif ($StartCount -eq 0 -and $EndCount -eq 0) {
            $WithoutOldRule = $Existing.TrimEnd()
        } else {
            throw "Refusing to update $AgentsFile because managed block markers are incomplete, duplicated, or out of order."
        }
        if ([string]::IsNullOrWhiteSpace($WithoutOldRule)) {
            $Updated = $Rule.TrimStart()
        } else {
            $Updated = $WithoutOldRule + [Environment]::NewLine + $Rule
        }
        Set-Content -Path $AgentsFile -Value $Updated -Encoding utf8
        Write-Host "Added or updated the optional global project-workflow rule in $AgentsFile"
    }

    Write-Host "Restart ChatGPT/Codex if the skill does not appear immediately."
    Write-Host 'Invoke with @agent-project-bootstrap in ChatGPT or $agent-project-bootstrap in Codex.'
    Write-Host 'In Codex CLI/IDE, use /prompts:integrate for the deprecated custom-prompt shortcut.'
}
finally {
    if ($null -ne $TemporaryDirectory -and (Test-Path $TemporaryDirectory)) {
        Remove-Item -Recurse -Force $TemporaryDirectory
    }
}
