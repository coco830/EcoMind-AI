# Agent Operations

This directory holds project-local agent routing artifacts.

## Skills Index

`skills-index.md` is generated from the current user and project skill roots. Do not edit it by hand.

Regenerate it after adding, removing, or editing `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, or agent operation scripts:

```powershell
python .\verify.py agents --write
python .\verify.py agents
```

When a task is unclear, complex, or needs a specialized workflow, search the index first:

```powershell
rg "<keyword>" docs/agents/skills-index.md
```

Open only the matching skill or protocol document needed for the task.

