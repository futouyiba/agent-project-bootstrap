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
        $SkillSource = Join-Path (Resolve-Path $Source) "skill"
    } else {
        $TemporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("agent-project-bootstrap-" + [guid]::NewGuid())
        New-Item -ItemType Directory -Path $TemporaryDirectory | Out-Null
        $ArchivePath = Join-Path $TemporaryDirectory "source.zip"
        $ArchiveUrl = "https://github.com/$RepositorySlug/archive/refs/heads/$RepositoryRef.zip"
        Invoke-WebRequest -Uri $ArchiveUrl -OutFile $ArchivePath
        Expand-Archive -Path $ArchivePath -DestinationPath $TemporaryDirectory
        $SkillSource = Join-Path $TemporaryDirectory "agent-project-bootstrap-$RepositoryRef/skill"
    }

    if (-not (Test-Path (Join-Path $SkillSource "SKILL.md")) -or
        -not (Test-Path (Join-Path $SkillSource "agents/openai.yaml"))) {
        throw "Invalid source: expected an installable skill at $SkillSource"
    }

    $SkillsRoot = Join-Path $CodexRoot "skills"
    $Destination = Join-Path $SkillsRoot "agent-project-bootstrap"
    New-Item -ItemType Directory -Force -Path $SkillsRoot | Out-Null

    if (Test-Path $Destination) {
        $Timestamp = Get-Date -Format "yyyyMMddHHmmss"
        $Backup = "$Destination.backup.$Timestamp"
        Move-Item -Path $Destination -Destination $Backup
        Write-Host "Existing installation backed up to $Backup"
    }

    Copy-Item -Recurse -Path $SkillSource -Destination $Destination
    Write-Host "Installed agent-project-bootstrap to $Destination"

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
- Treat `记一下`, `收需求`, `开始做`, and `收尾` as shortcuts for the `agent-project-bootstrap` daily flow.
- Keep repository-specific Project URLs, status names, test commands, and standing authorization in the repository `AGENTS.md`; repository rules take precedence.
- Global guidance alone never authorizes scope changes, deletion, merge, publishing, or deployment.
<!-- agent-project-bootstrap:end -->
'@
        $Pattern = '(?s)\s*<!-- agent-project-bootstrap:start -->.*?<!-- agent-project-bootstrap:end -->\s*'
        $WithoutOldRule = [regex]::Replace($Existing, $Pattern, "").TrimEnd()
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
}
finally {
    if ($null -ne $TemporaryDirectory -and (Test-Path $TemporaryDirectory)) {
        Remove-Item -Recurse -Force $TemporaryDirectory
    }
}
