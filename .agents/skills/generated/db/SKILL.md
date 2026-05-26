---
name: db
description: "Skill for the Db area of EcoMind-AI. 39 symbols across 4 files."
---

# Db

39 symbols | 4 files | Cohesion: 77%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how inject_mock_data, get_tdengine_client, tdengine_lifespan work
- Modifying db-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/db/tdengine_client.py` | _get_http_client, connect, sanitize_identifier, execute, init_database (+11) |
| `backend-cloudrun/app/db/postgres.py` | _ensure_regulator_scope_columns, _ensure_video_columns, _ensure_sqlite_columns, _ensure_sqlite_table_columns, _ensure_mysql_columns (+11) |
| `backend-cloudrun/app/db/tdengine.py` | get_tdengine_client, __init__, tdengine_lifespan, execute, query |
| `backend-cloudrun/app/api/v1/ai.py` | _generate_periodic_value, inject_mock_data |

## Entry Points

Start here when exploring this area:

- **`inject_mock_data`** (Function) — `backend-cloudrun/app/api/v1/ai.py:362`
- **`get_tdengine_client`** (Function) — `backend-cloudrun/app/db/tdengine.py:12`
- **`tdengine_lifespan`** (Function) — `backend-cloudrun/app/db/tdengine.py:125`
- **`get_tdengine_client`** (Function) — `backend-cloudrun/app/db/tdengine_client.py:821`
- **`check_schema`** (Function) — `backend-cloudrun/app/db/postgres.py:135`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `inject_mock_data` | Function | `backend-cloudrun/app/api/v1/ai.py` | 362 |
| `get_tdengine_client` | Function | `backend-cloudrun/app/db/tdengine.py` | 12 |
| `tdengine_lifespan` | Function | `backend-cloudrun/app/db/tdengine.py` | 125 |
| `get_tdengine_client` | Function | `backend-cloudrun/app/db/tdengine_client.py` | 821 |
| `check_schema` | Function | `backend-cloudrun/app/db/postgres.py` | 135 |
| `init_db` | Function | `backend-cloudrun/app/db/postgres.py` | 162 |
| `connect` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 79 |
| `sanitize_identifier` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 144 |
| `execute` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 188 |
| `init_database` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 251 |
| `alter_table_add_columns` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 317 |
| `insert_monitoring_data` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 352 |
| `insert_wide_monitoring_data` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 414 |
| `query_monitoring_data` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 584 |
| `get_statistics` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 730 |
| `escape_string` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 155 |
| `format_value` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 169 |
| `query_wide_monitoring_data` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 514 |
| `get_latest_values` | Method | `backend-cloudrun/app/db/tdengine_client.py` | 671 |
| `execute` | Method | `backend-cloudrun/app/db/tdengine.py` | 28 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Lifespan → _is_production` | cross_community | 5 |
| `Inject_historical_data_batch → _get_http_client` | cross_community | 5 |
| `Inject_historical_data_batch → Escape_string` | cross_community | 5 |
| `Lifespan → _load_model_metadata` | cross_community | 4 |
| `Init_database → _get_http_client` | intra_community | 4 |
| `Init_database → Escape_string` | cross_community | 4 |
| `Get_latest_values → _get_http_client` | cross_community | 4 |
| `Get_latest_values → Escape_string` | cross_community | 4 |
| `Inject_historical_data_batch → Sanitize_identifier` | cross_community | 4 |
| `Alter_table_add_columns → _get_http_client` | intra_community | 4 |

## How to Explore

1. `gitnexus_context({name: "inject_mock_data"})` — see callers and callees
2. `gitnexus_query({query: "db"})` — find related execution flows
3. Read key files listed above for implementation details
