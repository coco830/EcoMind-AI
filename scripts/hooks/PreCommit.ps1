. "$PSScriptRoot\Shared.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (Test-SkipProjectHooks) {
  Write-Host "Skipping project pre-commit hook."
  exit 0
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$branch = Get-CurrentBranch
if (Test-ProtectedBranch $branch) {
  Write-Error "Refusing commit on protected branch '$branch'. Create a task branch or worktree first."
  exit 1
}

$staged = @(Get-StagedFiles)
if ($staged.Count -eq 0) {
  Write-Host "No staged files."
  exit 0
}

$blockedPatterns = @(
  '^\.env($|\.|/)',
  '(^|/)\.env($|\.)',
  '^backend-cloudrun/\.env$',
  '^target/',
  '/target/',
  '^dist/',
  '/dist/',
  '^build/',
  '/build/',
  '^node_modules/',
  '/node_modules/',
  '^coverage/',
  '/coverage/',
  '^htmlcov/',
  '/htmlcov/',
  '^\.pytest_cache/',
  '/\.pytest_cache/',
  '^\.mypy_cache/',
  '/\.mypy_cache/',
  '^\.venv/',
  '/\.venv/',
  '^logs/',
  '/logs/',
  '\.log$',
  '\.tmp$',
  '\.sqlite$',
  '\.db$'
)

$blocked = @()
foreach ($file in $staged) {
  $normalized = $file -replace '\\', '/'
  foreach ($pattern in $blockedPatterns) {
    if ($normalized -match $pattern) {
      $blocked += $file
      break
    }
  }
}

if ($blocked.Count -gt 0) {
  Write-Error "Blocked staged files:`n$($blocked -join "`n")"
  Write-Error "Unstage generated, log, temp, local database, dependency, or env files."
  exit 1
}

$secretPatterns = @(
  '-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----',
  'AKIA[0-9A-Z]{16}',
  'AIza[0-9A-Za-z\-_]{35}',
  'ghp_[0-9A-Za-z]{36,}',
  'github_pat_[0-9A-Za-z_]{80,}',
  'sk-[A-Za-z0-9]{32,}',
  '(?i)(secret|token|api[_-]?key|access[_-]?key|private[_-]?key|password)\s*[:=]\s*[''"][^''"]{16,}[''"]'
)

$matches = @()
foreach ($file in $staged) {
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
    continue
  }
  if (-not (Test-TextFile $file)) {
    continue
  }
  $found = Select-String -LiteralPath $file -Pattern $secretPatterns -ErrorAction SilentlyContinue
  if ($found) {
    $matches += $found
  }
}

if ($matches.Count -gt 0) {
  $matches | Select-Object Path, LineNumber, Line | Format-Table -AutoSize
  Write-Error "Potential secret patterns found in staged files."
  exit 1
}

$stagedFeatureSpecs = @($staged | Where-Object { ($_ -replace '\\', '/') -match '^specs/.+\.feature$' })
if ($stagedFeatureSpecs.Count -gt 0) {
  Write-Host "Staged Gherkin specs detected; running project gate: python .\verify.py spec"
  & python .\verify.py spec
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

$agentOpsSensitivePatterns = @(
  '^AGENTS\.md$',
  '^CLAUDE\.md$',
  '^docs/agents/',
  '^scripts/agent-ops/',
  '^\.agents/',
  '^\.claude/skills/',
  '(^|/)SKILL\.md$'
)

$agentOpsTouched = @()
foreach ($file in $staged) {
  $normalized = $file -replace '\\', '/'
  foreach ($pattern in $agentOpsSensitivePatterns) {
    if ($normalized -match $pattern) {
      $agentOpsTouched += $file
      break
    }
  }
}

if ($agentOpsTouched.Count -gt 0) {
  Write-Host "Agent routing inputs changed; refreshing docs/agents/skills-index.md"
  & python .\verify.py agents --write
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }

  $skillsIndexStatus = @(git status --porcelain -- docs/agents/skills-index.md)
  $skillsIndexNeedsStaging = $false
  foreach ($line in $skillsIndexStatus) {
    if ($line.StartsWith("??") -or ($line.Length -ge 2 -and $line[1] -ne " ")) {
      $skillsIndexNeedsStaging = $true
      break
    }
  }

  if ($skillsIndexNeedsStaging) {
    Write-Error "docs/agents/skills-index.md was refreshed. Review and stage it before committing."
    exit 1
  }

  & python .\verify.py agents
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

$docsDrift = Join-Path $PSScriptRoot "Check-DocsDrift.ps1"
if (Test-Path -LiteralPath $docsDrift -PathType Leaf) {
  & $docsDrift -StagedFiles $staged
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

Write-Host "project pre-commit PASS"
