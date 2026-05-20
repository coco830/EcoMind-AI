# LSP Setup

## Purpose

Language servers let agents and editors navigate by symbols, definitions, references, diagnostics, and project types instead of relying only on text search.

## Python Backend

Recommended editor server: Pylance/Pyright.

Project configuration:

- Root `pyrightconfig.json`
- Backend source path: `backend-cloudrun`
- Optional local virtual environment: `backend-cloudrun/.venv`

Setup:

```powershell
cd E:\EcoMind-AI\backend-cloudrun
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
cd ..
npx --yes pyright --project .\pyrightconfig.json
```

`requirements-test.txt` is intentionally lighter than production dependencies. If editing modules that import optional production services such as COS/SMS/Prophet/H3, install `requirements-cloudbase.txt` into the same venv before relying on import diagnostics.

The initial Pyright baseline uses `typeCheckingMode: off` because the existing backend has historical type debt that is outside the guardrail setup scope. This still gives editors symbol navigation, import resolution, syntax diagnostics, and gradual LSP coverage. Tighten to `basic` only after the existing type errors are paid down in focused slices.

## Vue Console

Recommended editor extensions:

- Vue - Official / Volar
- TypeScript Vue Plugin if your editor needs it separately

Setup:

```powershell
cd E:\EcoMind-AI\frontend
npm install
npm run build
```

The package has `tsconfig.json` and `tsconfig.node.json`; Volar and TypeScript LSP should use the workspace TypeScript version.

## React Login Shell

Recommended editor extensions:

- TypeScript and JavaScript language features
- ESLint if linting is later added

Setup:

```powershell
cd E:\EcoMind-AI\ecosense-login
npm install
npm run build
```

## Unified Verification

From the repository root:

```powershell
python .\verify.py lsp
python .\verify.py check
```

`verify.py lsp` runs Pyright and available frontend type/build checks. If a package has no `node_modules`, it reports the missing dependency install instead of guessing global tooling.
