---
name: v1
description: "Skill for the V1 area of EcoMind-AI. 98 symbols across 22 files."
---

# V1

98 symbols | 22 files | Cohesion: 79%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how can_cross_tenant_doc_write, create_report, list_reports work
- Modifying v1-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/api/v1/self_inspection.py` | _get_user_org_id, create_report, list_reports, get_report, update_report (+15) |
| `backend-cloudrun/app/api/v1/alarms.py` | _build_org_filter_query, list_alarms, list_pending_alarms, get_alarm_stats, _check_alarm_access (+4) |
| `backend-cloudrun/app/services/self_inspection_service.py` | create_report, get_report, list_reports, update_report, delete_report (+3) |
| `backend-cloudrun/app/api/v1/data.py` | _verify_device_access, _get_accessible_device_ids, query_monitoring_data, get_latest_data, get_realtime_data (+3) |
| `backend-cloudrun/app/core/rate_limiter.py` | _is_testing, _get_rate_limit_key, _get_user_date_key, check_device_cooldown, check_user_quota (+3) |
| `backend-cloudrun/app/api/v1/invitations.py` | generate_invitation_code, _invitation_to_response, create_invitation_code, list_invitation_codes, get_invitation_code (+2) |
| `backend-cloudrun/app/api/v1/devices.py` | get_device_stats, _deserialize_thresholds, _device_to_response, list_devices, get_device |
| `backend-cloudrun/app/api/v1/ai.py` | check_rate_limit_status, _extract_video_risk_assessment_from_snapshot, get_cached_report, diagnose_db_status, mask_password |
| `backend-cloudrun/app/api/deps.py` | can_cross_tenant_doc_write, _is_platform_staff, can_cross_tenant_read, require_platform_staff_read |
| `backend-cloudrun/app/api/v1/dashboard.py` | get_dashboard_stats, get_device_pollutants, get_trend_data, get_realtime_data |

## Entry Points

Start here when exploring this area:

- **`can_cross_tenant_doc_write`** (Function) — `backend-cloudrun/app/api/deps.py:40`
- **`create_report`** (Function) — `backend-cloudrun/app/api/v1/self_inspection.py:546`
- **`list_reports`** (Function) — `backend-cloudrun/app/api/v1/self_inspection.py:600`
- **`get_report`** (Function) — `backend-cloudrun/app/api/v1/self_inspection.py:1016`
- **`update_report`** (Function) — `backend-cloudrun/app/api/v1/self_inspection.py:1070`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `OpsBriefListItemResponse` | Class | `backend-cloudrun/app/api/v1/self_inspection.py` | 93 |
| `OpsBriefResponse` | Class | `backend-cloudrun/app/api/v1/self_inspection.py` | 104 |
| `can_cross_tenant_doc_write` | Function | `backend-cloudrun/app/api/deps.py` | 40 |
| `create_report` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 546 |
| `list_reports` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 600 |
| `get_report` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 1016 |
| `update_report` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 1070 |
| `delete_report` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 1136 |
| `generate_ops_brief` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 1163 |
| `list_ops_brief_history` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 1225 |
| `get_trend_analysis` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 1332 |
| `generate_ai_report` | Function | `backend-cloudrun/app/api/v1/self_inspection.py` | 1357 |
| `get_spark_client` | Function | `backend-cloudrun/app/services/llm/__init__.py` | 6 |
| `get_self_inspection_service` | Function | `backend-cloudrun/app/services/self_inspection_service.py` | 1173 |
| `get_ai_data_extractor` | Function | `backend-cloudrun/app/services/self_inspection_service.py` | 1192 |
| `can_cross_tenant_read` | Function | `backend-cloudrun/app/api/deps.py` | 35 |
| `require_platform_staff_read` | Function | `backend-cloudrun/app/api/deps.py` | 110 |
| `list_alarms` | Function | `backend-cloudrun/app/api/v1/alarms.py` | 47 |
| `list_pending_alarms` | Function | `backend-cloudrun/app/api/v1/alarms.py` | 93 |
| `get_alarm_stats` | Function | `backend-cloudrun/app/api/v1/alarms.py` | 329 |

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
| Services | 6 calls |
| Openapi | 4 calls |

## How to Explore

1. `gitnexus_context({name: "can_cross_tenant_doc_write"})` — see callers and callees
2. `gitnexus_query({query: "v1"})` — find related execution flows
3. Read key files listed above for implementation details
