Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
if ([string]::IsNullOrWhiteSpace($repoRoot)) {
  throw "Not inside a Git repository."
}

Set-Location $repoRoot
git config core.hooksPath .githooks
Write-Host "Installed project Git hooks: core.hooksPath=.githooks"
