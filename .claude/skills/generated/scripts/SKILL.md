---
name: scripts
description: "Skill for the Scripts area of EcoMind-AI. 42 symbols across 9 files."
---

# Scripts

42 symbols | 9 files | Cohesion: 95%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how get_user_specs, main, register work
- Modifying scripts-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/scripts/init_users.py` | _is_production_environment, _resolve_password, get_user_specs, _now_utc_naive, _build_db_url_from_env (+8) |
| `scripts/check_specs.py` | fail, find_features, check_basic_shape, resolve_gherkin, check_with_gherkin (+1) |
| `backend-cloudrun/scripts/tcp_to_http_proxy.py` | start, stop, main, _handle_connection, _forward_to_cloudbase |
| `backend-cloudrun/scripts/inject_mock_history.py` | generate_periodic_value, inject_historical_data_batch, plot_preview, main |
| `backend-cloudrun/scripts/pick_test_mn_code.py` | _build_db_url_from_env, _normalize_async_url, _pick_one, _main |
| `backend-cloudrun/scripts/verify_db_automation.py` | _base_env, _run_case, _sqlite_url, main |
| `backend-cloudrun/scripts/init_superadmin.py` | _is_production_environment, get_superadmin_password, create_superadmin |
| `backend-cloudrun/app/api/v1/auth.py` | register, reset_password |
| `backend-cloudrun/app/core/security.py` | get_password_hash |

## Entry Points

Start here when exploring this area:

- **`get_user_specs`** (Function) — `backend-cloudrun/scripts/init_users.py:93`
- **`main`** (Function) — `backend-cloudrun/scripts/init_users.py:457`
- **`register`** (Function) — `backend-cloudrun/app/api/v1/auth.py:100`
- **`reset_password`** (Function) — `backend-cloudrun/app/api/v1/auth.py:289`
- **`get_password_hash`** (Function) — `backend-cloudrun/app/core/security.py:34`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_user_specs` | Function | `backend-cloudrun/scripts/init_users.py` | 93 |
| `main` | Function | `backend-cloudrun/scripts/init_users.py` | 457 |
| `register` | Function | `backend-cloudrun/app/api/v1/auth.py` | 100 |
| `reset_password` | Function | `backend-cloudrun/app/api/v1/auth.py` | 289 |
| `get_password_hash` | Function | `backend-cloudrun/app/core/security.py` | 34 |
| `get_superadmin_password` | Function | `backend-cloudrun/scripts/init_superadmin.py` | 47 |
| `create_superadmin` | Function | `backend-cloudrun/scripts/init_superadmin.py` | 58 |
| `fail` | Function | `scripts/check_specs.py` | 14 |
| `find_features` | Function | `scripts/check_specs.py` | 18 |
| `check_basic_shape` | Function | `scripts/check_specs.py` | 24 |
| `resolve_gherkin` | Function | `scripts/check_specs.py` | 39 |
| `check_with_gherkin` | Function | `scripts/check_specs.py` | 57 |
| `main` | Function | `scripts/check_specs.py` | 98 |
| `generate_periodic_value` | Function | `backend-cloudrun/scripts/inject_mock_history.py` | 31 |
| `inject_historical_data_batch` | Function | `backend-cloudrun/scripts/inject_mock_history.py` | 128 |
| `plot_preview` | Function | `backend-cloudrun/scripts/inject_mock_history.py` | 253 |
| `main` | Function | `backend-cloudrun/scripts/inject_mock_history.py` | 286 |
| `main` | Function | `backend-cloudrun/scripts/verify_db_automation.py` | 54 |
| `main` | Function | `backend-cloudrun/scripts/tcp_to_http_proxy.py` | 204 |
| `start` | Method | `backend-cloudrun/scripts/tcp_to_http_proxy.py` | 75 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → _is_production_environment` | intra_community | 5 |
| `Inject_historical_data_batch → _get_http_client` | cross_community | 5 |
| `Inject_historical_data_batch → Escape_string` | cross_community | 5 |
| `Main → _now_utc_naive` | intra_community | 4 |
| `Inject_historical_data_batch → Sanitize_identifier` | cross_community | 4 |
| `Lifespan → Get_password_hash` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Db | 4 calls |

## How to Explore

1. `gitnexus_context({name: "get_user_specs"})` — see callers and callees
2. `gitnexus_query({query: "scripts"})` — find related execution flows
3. Read key files listed above for implementation details
