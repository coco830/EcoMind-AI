. "$PSScriptRoot\Shared.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (Test-SkipProjectHooks) {
  Write-Host "Skipping project post-merge hook."
  exit 0
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$branch = Get-CurrentBranch
if ($branch -ne "main") {
  Write-Host "project post-merge cleanup skipped: current branch is '$branch', not 'main'."
  exit 0
}

& pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "Cleanup-MergedBranches.ps1") -IncludeRemote -IncludeWorktrees
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
