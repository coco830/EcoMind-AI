# Git Hooks

## Installation

Project hooks live in `.githooks/` and call PowerShell implementations from `scripts/hooks/`.

Install them for this repository:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\hooks\Install-GitHooks.ps1
```

This sets:

```powershell
git config core.hooksPath .githooks
```

## Hooks

- `pre-commit`
  - Blocks commits on protected branches.
  - Blocks staged env files, logs, generated output, dependency folders, coverage, temp files, and local databases.
  - Scans staged text files for common secret patterns.
  - Warns when staged implementation/tooling changes may require updates to `CODEMAP.md`, `AGENTS.md`, architecture, LSP, Git hook, database automation, or README docs.

- `commit-msg`
  - Blocks empty commit messages.
  - Blocks subjects longer than 120 characters.
  - Blocks vague subjects such as `wip`, `tmp`, `test`, `fix`, or `update`.

- `pre-push`
  - Blocks pushes from protected branches unless a human has explicitly approved the mainline push.
  - Runs `python .\verify.py check`.
  - For human-approved protected branch pushes, also runs `python .\verify.py test`.

Human-approved protected branch push:

```powershell
$env:HUMAN_APPROVED_MAIN_PUSH = "1"
git push origin main
Remove-Item Env:\HUMAN_APPROVED_MAIN_PUSH
```

- `post-merge`
  - Runs only when the current branch is `main`.
  - Deletes local and remote branches already merged into `main`.
  - Removes clean auxiliary worktrees.
  - Keeps unmerged branches and dirty worktrees.

## Bypass

Use only when you understand the risk:

```powershell
$env:SKIP_PROJECT_GIT_HOOKS = "1"
```

Remove it afterward:

```powershell
Remove-Item Env:\SKIP_PROJECT_GIT_HOOKS
```

Docs drift warnings can be made strict for a shell:

```powershell
$env:DOCS_DRIFT_STRICT = "1"
```

To skip only the docs drift reminder:

```powershell
$env:SKIP_DOCS_DRIFT_HOOK = "1"
```
