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

Write-Host "project pre-commit PASS"
