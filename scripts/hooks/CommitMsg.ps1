param(
  [Parameter(Mandatory = $true)]
  [string]$MessageFile
)

. "$PSScriptRoot\Shared.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (Test-SkipProjectHooks) {
  Write-Host "Skipping project commit-msg hook."
  exit 0
}

$message = (Get-Content -Raw -LiteralPath $MessageFile).Trim()
if ([string]::IsNullOrWhiteSpace($message)) {
  Write-Error "Commit message is empty."
  exit 1
}

$firstLine = ($message -split "`r?`n")[0].Trim()
if ($firstLine.Length -gt 120) {
  Write-Error "Commit subject is longer than 120 characters."
  exit 1
}

if ($firstLine -match '^\s*(wip|tmp|test|fix|update|changes?)\s*$') {
  Write-Error "Commit subject is too vague: '$firstLine'. Use a concrete summary."
  exit 1
}

Write-Host "project commit-msg PASS"
