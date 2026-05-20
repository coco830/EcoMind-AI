. "$PSScriptRoot\Shared.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (Test-SkipProjectHooks) {
  Write-Host "Skipping project pre-push hook."
  exit 0
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$branch = Get-CurrentBranch
if (Test-ProtectedBranch $branch) {
  Write-Error "Refusing push from protected branch '$branch'."
  exit 1
}

Write-Host "Running project gate: python .\verify.py check"
& python .\verify.py check
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

Write-Host "project pre-push PASS"
