---
name: cluster-82
description: "Skill for the Cluster_82 area of EcoMind-AI. 4 symbols across 1 files."
---

# Cluster_82

4 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how validate_postgres_password, validate_jwt_secret, validate_sm4_key work
- Modifying cluster_82-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/core/config.py` | _is_production_environment, validate_postgres_password, validate_jwt_secret, validate_sm4_key |

## Entry Points

Start here when exploring this area:

- **`validate_postgres_password`** (Method) — `backend-cloudrun/app/core/config.py:94`
- **`validate_jwt_secret`** (Method) — `backend-cloudrun/app/core/config.py:147`
- **`validate_sm4_key`** (Method) — `backend-cloudrun/app/core/config.py:196`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `validate_postgres_password` | Method | `backend-cloudrun/app/core/config.py` | 94 |
| `validate_jwt_secret` | Method | `backend-cloudrun/app/core/config.py` | 147 |
| `validate_sm4_key` | Method | `backend-cloudrun/app/core/config.py` | 196 |
| `_is_production_environment` | Function | `backend-cloudrun/app/core/config.py` | 18 |

## How to Explore

1. `gitnexus_context({name: "validate_postgres_password"})` — see callers and callees
2. `gitnexus_query({query: "cluster_82"})` — find related execution flows
3. Read key files listed above for implementation details
