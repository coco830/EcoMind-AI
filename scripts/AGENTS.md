# Scripts Agent Guide

## Scope

`scripts` contains project automation, including Git hook implementations.

## Rules

- Keep hook scripts deterministic and Windows-friendly.
- Hooks should block clear safety problems and avoid guessing project-specific heavyweight commands outside `verify.py`.
- Use `SKIP_PROJECT_GIT_HOOKS=1` only for intentional bypasses.
- Keep `docs/GIT_HOOKS.md` updated when hook behavior changes.
