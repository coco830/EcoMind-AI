Set-StrictMode -Version Latest

function Get-RepoRoot {
  $root = (& git rev-parse --show-toplevel 2>$null)
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($root)) {
    throw "Not inside a Git repository."
  }
  return $root.Trim()
}

function Get-CurrentBranch {
  $branch = (& git branch --show-current 2>$null)
  if ($LASTEXITCODE -ne 0) {
    return ""
  }
  return $branch.Trim()
}

function Test-ProtectedBranch([string]$Branch) {
  $protected = @("main", "master", "trunk", "dev", "develop")
  return $protected -contains $Branch
}

function Test-SkipProjectHooks {
  return $env:SKIP_PROJECT_GIT_HOOKS -eq "1" -or $env:SKIP_VERIFY_HOOKS -eq "1"
}

function Get-StagedFiles {
  $files = & git diff --cached --name-only --diff-filter=ACMR
  if (-not $files) {
    return @()
  }
  return @($files)
}

function Test-TextFile([string]$Path) {
  try {
    $resolved = Resolve-Path -LiteralPath $Path
    $bytes = [System.IO.File]::ReadAllBytes($resolved)
    $sampleLength = [Math]::Min($bytes.Length, 4096)
    for ($i = 0; $i -lt $sampleLength; $i++) {
      if ($bytes[$i] -eq 0) {
        return $false
      }
    }
    return $true
  } catch {
    return $false
  }
}
