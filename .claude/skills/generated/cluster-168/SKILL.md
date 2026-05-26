---
name: cluster-168
description: "Skill for the Cluster_168 area of EcoMind-AI. 17 symbols across 1 files."
---

# Cluster_168

17 symbols | 1 files | Cohesion: 100%

## When to Use

- Understanding how run, command_exists, python_executable work
- Modifying cluster_168-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `verify.py` | run, command_exists, python_executable, npm_command, npx_command (+12) |

## Entry Points

Start here when exploring this area:

- **`run`** (Function) — `verify.py:16`
- **`command_exists`** (Function) — `verify.py:30`
- **`python_executable`** (Function) — `verify.py:34`
- **`npm_command`** (Function) — `verify.py:41`
- **`npx_command`** (Function) — `verify.py:45`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `run` | Function | `verify.py` | 16 |
| `command_exists` | Function | `verify.py` | 30 |
| `python_executable` | Function | `verify.py` | 34 |
| `npm_command` | Function | `verify.py` | 41 |
| `npx_command` | Function | `verify.py` | 45 |
| `compile_python` | Function | `verify.py` | 49 |
| `test_backend` | Function | `verify.py` | 53 |
| `pyright` | Function | `verify.py` | 62 |
| `frontend_typecheck` | Function | `verify.py` | 69 |
| `login_typecheck` | Function | `verify.py` | 76 |
| `check` | Function | `verify.py` | 83 |
| `lsp` | Function | `verify.py` | 93 |
| `test` | Function | `verify.py` | 100 |
| `spec` | Function | `verify.py` | 105 |
| `db` | Function | `verify.py` | 110 |
| `security` | Function | `verify.py` | 115 |
| `all_checks` | Function | `verify.py` | 120 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `All_checks → Run` | intra_community | 4 |
| `All_checks → Python_executable` | intra_community | 4 |
| `All_checks → Command_exists` | intra_community | 4 |
| `All_checks → Npx_command` | intra_community | 4 |
| `Lsp → Command_exists` | intra_community | 3 |
| `Lsp → Npx_command` | intra_community | 3 |
| `Lsp → Run` | intra_community | 3 |
| `Lsp → Npm_command` | intra_community | 3 |

## How to Explore

1. `gitnexus_context({name: "run"})` — see callers and callees
2. `gitnexus_query({query: "cluster_168"})` — find related execution flows
3. Read key files listed above for implementation details
