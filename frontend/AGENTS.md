# Frontend Agent Guide

## Scope

`frontend` is the Vue 3 enterprise operations console. It uses Vite, TypeScript, Vue Router, Pinia, Element Plus, ECharts, Leaflet, and Tailwind.

## Commands

```powershell
npm install
npm run build
```

From the repository root:

```powershell
python .\verify.py lsp
```

## Rules

- Keep enterprise compliance/risk wording aligned with backend domain language.
- Do not present video or AI risk summaries as official regulatory conclusions.
- Use the existing `@/* -> src/*` alias.
- Keep API client changes aligned with `backend-cloudrun/app/api`.
- Do not commit `dist/`, `node_modules/`, logs, local env files, or generated videos.
