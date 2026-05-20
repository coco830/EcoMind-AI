param(
  [switch]$IncludeRemote,
  [switch]$IncludeWorktrees
)

. "$PSScriptRoot\Shared.ps1"

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

$currentBranch = Get-CurrentBranch
if ($currentBranch -ne "main") {
  throw "Cleanup must run from main. Current branch: '$currentBranch'."
}

& git fetch --prune origin 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "No fetchable origin or fetch failed; continuing with local cleanup only."
}

function Test-IsAncestorOfMain([string]$Ref) {
  & git merge-base --is-ancestor $Ref main 2>$null
  return $LASTEXITCODE -eq 0
}

Write-Host ""
Write-Host "== cleanup: merged local branches =="
$localBranches = @(
  & git for-each-ref refs/heads --format="%(refname:short)" |
    Where-Object { $_ -and $_ -ne "main" }
)
$deletedLocal = 0
foreach ($branch in $localBranches) {
  if (Test-IsAncestorOfMain $branch) {
    & git branch -d $branch
    if ($LASTEXITCODE -ne 0) {
      throw "Failed to delete local branch '$branch'."
    }
    $deletedLocal++
  } else {
    Write-Host "keep local unmerged: $branch"
  }
}
Write-Host "Deleted local merged branches: $deletedLocal"

if ($IncludeRemote) {
  Write-Host ""
  Write-Host "== cleanup: merged remote branches =="
  $remoteBranches = @(
    & git for-each-ref refs/remotes/origin --format="%(refname:short)" |
      Where-Object { $_ -and $_ -ne "origin" -and $_ -ne "origin/main" -and $_ -ne "origin/HEAD" }
  )
  $deletedRemote = 0
  foreach ($remoteRef in $remoteBranches) {
    if (Test-IsAncestorOfMain $remoteRef) {
      $remoteBranch = $remoteRef.Substring("origin/".Length)
      $previousSkip = $env:SKIP_PROJECT_GIT_HOOKS
      $env:SKIP_PROJECT_GIT_HOOKS = "1"
      & git push origin --delete $remoteBranch
      if ([string]::IsNullOrEmpty($previousSkip)) {
        Remove-Item Env:\SKIP_PROJECT_GIT_HOOKS -ErrorAction SilentlyContinue
      } else {
        $env:SKIP_PROJECT_GIT_HOOKS = $previousSkip
      }
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to delete remote branch '$remoteBranch'."
      }
      $deletedRemote++
    } else {
      Write-Host "keep remote unmerged: $remoteRef"
    }
  }
  Write-Host "Deleted remote merged branches: $deletedRemote"
}

if ($IncludeWorktrees) {
  Write-Host ""
  Write-Host "== cleanup: auxiliary worktrees =="
  $worktreeLines = @(& git worktree list --porcelain)
  $paths = New-Object System.Collections.Generic.List[string]
  foreach ($line in $worktreeLines) {
    if ($line -like "worktree *") {
      $path = $line.Substring("worktree ".Length)
      if (-not $path) {
        continue
      }
      $resolvedPath = (Resolve-Path -LiteralPath $path).Path
      $resolvedRoot = (Resolve-Path -LiteralPath $repoRoot).Path
      if ($resolvedPath -ne $resolvedRoot) {
        $paths.Add($path)
      }
    }
  }

  $removedWorktrees = 0
  foreach ($path in $paths) {
    $status = @(& git -C $path status --short)
    if ($status.Count -gt 0) {
      Write-Host "keep dirty worktree: $path"
      continue
    }
    & git worktree remove --force $path
    if ($LASTEXITCODE -ne 0) {
      throw "Failed to remove worktree '$path'."
    }
    $removedWorktrees++
  }
  & git worktree prune
  Write-Host "Removed clean auxiliary worktrees: $removedWorktrees"
}

Write-Host ""
Write-Host "Merged branch cleanup PASS"
