---
name: openapi
description: "Skill for the Openapi area of EcoMind-AI. 49 symbols across 13 files."
---

# Openapi

49 symbols | 13 files | Cohesion: 68%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how get_ai_prediction, create_device, update_device work
- Modifying openapi-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/api/openapi/integration_tools.py` | get_monitoring_summary, _integration_error, _parse_metadata, _extract_org_selector, _ensure_zip_file (+5) |
| `backend-cloudrun/app/api/openapi/schemas.py` | OpenApiResponse, DeviceStatusResponse, LatestDataResponse, ActiveAlarmsResponse, PredictionResponse (+4) |
| `backend-cloudrun/app/api/openapi/ai_tools.py` | _get_threshold_for_pollutant, _coerce_sort_key, _get_recent_pollutant_candidates, get_ai_prediction, _find_device_by_org (+3) |
| `backend-cloudrun/app/core/pollutant_library.py` | normalize_pollutant_code, get_pollutant_column_name, get_pollutant_name, is_known_pollutant |
| `backend-cloudrun/app/api/v1/devices.py` | _serialize_thresholds, create_device, update_device |
| `backend-cloudrun/app/api/openapi/alarm_tools.py` | acknowledge_alarm, _format_duration, get_active_alarms |
| `backend-cloudrun/app/services/cos_storage.py` | _sanitize_filename, build_key, put_bytes |
| `backend-cloudrun/app/api/openapi/auth.py` | resolve_target_org, require_tool_permission |
| `backend-cloudrun/app/api/openapi/data_tools.py` | _assess_compliance, get_latest_data |
| `backend-cloudrun/app/api/openapi/device_tools.py` | _format_heartbeat_duration, get_device_status |

## Entry Points

Start here when exploring this area:

- **`get_ai_prediction`** (Function) — `backend-cloudrun/app/api/openapi/ai_tools.py:126`
- **`create_device`** (Function) — `backend-cloudrun/app/api/v1/devices.py:212`
- **`update_device`** (Function) — `backend-cloudrun/app/api/v1/devices.py:298`
- **`normalize_pollutant_code`** (Function) — `backend-cloudrun/app/core/pollutant_library.py:212`
- **`get_pollutant_column_name`** (Function) — `backend-cloudrun/app/core/pollutant_library.py:298`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `OpenApiResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 20 |
| `DeviceStatusResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 76 |
| `LatestDataResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 109 |
| `ActiveAlarmsResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 154 |
| `PredictionResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 171 |
| `AiReportResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 186 |
| `MonitoringSummaryResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 215 |
| `PackagePushResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 224 |
| `PackagePushStatusResponse` | Class | `backend-cloudrun/app/api/openapi/schemas.py` | 229 |
| `get_ai_prediction` | Function | `backend-cloudrun/app/api/openapi/ai_tools.py` | 126 |
| `create_device` | Function | `backend-cloudrun/app/api/v1/devices.py` | 212 |
| `update_device` | Function | `backend-cloudrun/app/api/v1/devices.py` | 298 |
| `normalize_pollutant_code` | Function | `backend-cloudrun/app/core/pollutant_library.py` | 212 |
| `get_pollutant_column_name` | Function | `backend-cloudrun/app/core/pollutant_library.py` | 298 |
| `acknowledge_alarm` | Function | `backend-cloudrun/app/api/openapi/alarm_tools.py` | 154 |
| `resolve_target_org` | Function | `backend-cloudrun/app/api/openapi/auth.py` | 130 |
| `require_tool_permission` | Function | `backend-cloudrun/app/api/openapi/auth.py` | 207 |
| `get_latest_data` | Function | `backend-cloudrun/app/api/openapi/data_tools.py` | 49 |
| `get_device_status` | Function | `backend-cloudrun/app/api/openapi/device_tools.py` | 55 |
| `get_monitoring_summary` | Function | `backend-cloudrun/app/api/openapi/integration_tools.py` | 206 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Batch_generate_reports → _parse_aliases_from_string` | cross_community | 9 |
| `Generate_ops_brief → _parse_aliases_from_string` | cross_community | 7 |
| `Get_latest_data → _parse_aliases_from_string` | cross_community | 6 |
| `Get_active_alarms → _parse_aliases_from_string` | cross_community | 6 |
| `Get_latest_data → _parse_aliases_from_string` | cross_community | 6 |
| `Get_device_online_metrics → _parse_aliases_from_string` | cross_community | 6 |
| `Get_device_flow → _parse_aliases_from_string` | cross_community | 6 |
| `Query_monitoring_data → _parse_aliases_from_string` | cross_community | 6 |
| `Get_trend_data → _parse_aliases_from_string` | cross_community | 6 |
| `Get_device_pollutants → _parse_aliases_from_string` | cross_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Services | 7 calls |
| V1 | 3 calls |
| Gateway | 1 calls |
| Ai | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_ai_prediction"})` — see callers and callees
2. `gitnexus_query({query: "openapi"})` — find related execution flows
3. Read key files listed above for implementation details
