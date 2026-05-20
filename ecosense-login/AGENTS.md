# Ecosense Login Agent Guide

## Scope

`ecosense-login` is a small React/Vite entry or login shell.

## Commands

```powershell
npm install
npm run build
```

## Rules

- Keep this package small and focused on entry/login experience.
- Do not duplicate enterprise console workflows from `frontend/`.
- Keep environment values out of Git; commit examples only.
- If auth contract changes, update backend auth docs/tests and this package together.
