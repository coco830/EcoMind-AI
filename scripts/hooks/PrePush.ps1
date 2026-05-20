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
$isProtectedBranch = Test-ProtectedBranch $branch
$hasHumanApproval = $env:HUMAN_APPROVED_MAIN_PUSH -eq "1" -or $env:ALLOW_PROTECTED_BRANCH_PUSH -eq "1"

if ($isProtectedBranch -and -not $hasHumanApproval) {
  Write-Error "Refusing push from protected branch '$branch'. Set HUMAN_APPROVED_MAIN_PUSH=1 after human approval; this hook will still run verification before allowing the push."
  exit 1
}

if ($isProtectedBranch) {
  Write-Host "Human-approved protected branch push detected for '$branch'."
}

Write-Host "Running project gate: python .\verify.py check"
& python .\verify.py check
if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}

if ($isProtectedBranch) {
  Write-Host "Running protected-branch test gate: python .\verify.py test"
  & python .\verify.py test
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
}

Write-Host "project pre-push PASS"
