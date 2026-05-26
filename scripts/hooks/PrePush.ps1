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
$hasHumanApproval = $env:GIT_WORKFLOW_MAIN_SHIP -eq "1" -or $env:HUMAN_APPROVED_MAIN_PUSH -eq "1" -or $env:ALLOW_PROTECTED_BRANCH_PUSH -eq "1"

if ($isProtectedBranch -and -not $hasHumanApproval) {
  Write-Error "Refusing push from protected branch '$branch'. Set GIT_WORKFLOW_MAIN_SHIP=1 or HUMAN_APPROVED_MAIN_PUSH=1 only after human approval; this hook will still run verification before allowing the push."
  exit 1
}

if ($isProtectedBranch) {
  Write-Host "Human-approved protected branch push detected for '$branch'."
}

$upstream = (& git rev-parse --abbrev-ref --symbolic-full-name "@{u}" 2>$null)
$changedFeatureSpecs = @()
if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($upstream)) {
  $changedFeatureSpecs = @(git diff --name-only --diff-filter=ACMR "$($upstream.Trim())...HEAD" -- "specs/**/*.feature")
} else {
  & git rev-parse --verify origin/main 1>$null 2>$null
  if ($LASTEXITCODE -eq 0) {
    $changedFeatureSpecs = @(git diff --name-only --diff-filter=ACMR "origin/main...HEAD" -- "specs/**/*.feature")
  } else {
    $changedFeatureSpecs = @(git diff-tree --no-commit-id --name-only -r HEAD -- "specs/**/*.feature")
  }
}

if ($changedFeatureSpecs.Count -gt 0) {
  Write-Host "Changed Gherkin specs detected in push range; running project gate: python .\verify.py spec"
  & python .\verify.py spec
  if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
  }
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
