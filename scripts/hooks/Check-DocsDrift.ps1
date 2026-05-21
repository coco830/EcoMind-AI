param(
  [string[]]$StagedFiles = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($env:SKIP_DOCS_DRIFT_HOOK -eq "1") {
  Write-Host "Skipping docs drift check."
  exit 0
}

if ($StagedFiles.Count -eq 0) {
  $StagedFiles = @(git diff --cached --name-only --diff-filter=ACMR)
}

if ($StagedFiles.Count -eq 0) {
  exit 0
}

$impactPatterns = @(
  '^backend-cloudrun/',
  '^frontend/',
  '^ecosense-login/',
  '^scripts/hooks/',
  '^verify\.py$',
  '^pyrightconfig\.json$',
  '^requirements.*\.txt$',
  '^package(-lock)?\.json$'
)

$contextPatterns = @(
  '^AGENTS\.md$',
  '(^|/)AGENTS\.md$',
  '^CODEMAP\.md$',
  '^ARCHITECTURE\.md$',
  '^docs/ARCHITECTURE\.md$',
  '^docs/LSP\.md$',
  '^docs/GIT_HOOKS\.md$',
  '^docs/DB_AUTOMATION\.md$',
  '^README\.md$'
)

$impacted = @()
$context = @()
foreach ($file in $StagedFiles) {
  $normalized = $file -replace '\\', '/'
  foreach ($pattern in $impactPatterns) {
    if ($normalized -match $pattern) {
      $impacted += $file
      break
    }
  }
  foreach ($pattern in $contextPatterns) {
    if ($normalized -match $pattern) {
      $context += $file
      break
    }
  }
}

if ($impacted.Count -eq 0 -or $context.Count -gt 0) {
  Write-Host "docs drift check PASS"
  exit 0
}

$message = @"
Docs drift warning: staged implementation/tooling changes may need context updates.
Impacted files:
$($impacted -join "`n")

Consider staging relevant updates to CODEMAP.md, AGENTS.md, docs/ARCHITECTURE.md, docs/LSP.md, docs/GIT_HOOKS.md, docs/DB_AUTOMATION.md, or README.md.
Set DOCS_DRIFT_STRICT=1 to make this warning a hard gate.
"@

Write-Warning $message
if ($env:DOCS_DRIFT_STRICT -eq "1") {
  exit 1
}

exit 0
