---
name: services
description: "Skill for the Services area of EcoMind-AI. 251 symbols across 37 files."
---

# Services

251 symbols | 37 files | Cohesion: 88%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how get_regulator_overview, get_regulator_heatmap, get_regulator_trends work
- Modifying services-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/services/regulatory_service.py` | _resolve_target_date, _resolve_date_range, _resolve_month_range, _safe_divide, _risk_level (+25) |
| `backend-cloudrun/app/services/alarm_service.py` | get_pollutant_name, _get_session, _close_session, _find_active_alarm, _get_device_with_org (+17) |
| `backend-cloudrun/app/services/video_service.py` | _resolve_event, _event_to_response, list_events, acknowledge_event, resolve_event (+14) |
| `backend-cloudrun/app/services/video_risk_service.py` | format_for_prompt, _build_alarm_fallback_items, build_device_video_risk_assessment, _resolve_device, _list_channels (+12) |
| `backend-cloudrun/app/services/self_inspection_service.py` | _get_access_token, recognize_document, recognize_table, recognize_pdf_tables, parse_ocr_result (+12) |
| `backend-cloudrun/app/services/data_interpolation.py` | __init__, _normalize_frequency, interpolate, interpolate_hourly, prepare_for_prediction (+7) |
| `backend-cloudrun/app/services/data_analysis_service.py` | get_device_thresholds, get_device_industry_info, analyze_device_daily_stats, _generate_summary, analyze_device_daily_stats (+5) |
| `backend-cloudrun/app/services/scheduler.py` | _attach_video_prompt_context, generate_daily_report_for_device, generate_daily_reports_job, trigger_daily_reports_manually, aggregate_monitoring_data_job (+5) |
| `backend-cloudrun/app/api/v1/video.py` | list_video_events, acknowledge_video_event, resolve_video_event, list_video_channels, create_video_channel (+5) |
| `backend-cloudrun/app/core/prompts.py` | get_industry_knowledge, get_domain_from_device_type, get_domain_from_pollutant_code, get_domain_knowledge, get_pollutant_info (+4) |

## Entry Points

Start here when exploring this area:

- **`get_regulator_overview`** (Function) — `backend-cloudrun/app/api/v1/regulator.py:24`
- **`get_regulator_heatmap`** (Function) — `backend-cloudrun/app/api/v1/regulator.py:40`
- **`get_regulator_trends`** (Function) — `backend-cloudrun/app/api/v1/regulator.py:57`
- **`get_regulator_consistency`** (Function) — `backend-cloudrun/app/api/v1/regulator.py:75`
- **`download_regulator_report`** (Function) — `backend-cloudrun/app/api/v1/regulator.py:90`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_regulator_overview` | Function | `backend-cloudrun/app/api/v1/regulator.py` | 24 |
| `get_regulator_heatmap` | Function | `backend-cloudrun/app/api/v1/regulator.py` | 40 |
| `get_regulator_trends` | Function | `backend-cloudrun/app/api/v1/regulator.py` | 57 |
| `get_regulator_consistency` | Function | `backend-cloudrun/app/api/v1/regulator.py` | 75 |
| `download_regulator_report` | Function | `backend-cloudrun/app/api/v1/regulator.py` | 90 |
| `get_regulator_brief` | Function | `backend-cloudrun/app/api/v1/regulator.py` | 147 |
| `download_regulator_brief` | Function | `backend-cloudrun/app/api/v1/regulator.py` | 179 |
| `stream_ai_report` | Function | `backend-cloudrun/app/api/v1/ai.py` | 780 |
| `generate_ai_report_sync` | Function | `backend-cloudrun/app/api/v1/ai.py` | 840 |
| `generate_report_with_rate_limit` | Function | `backend-cloudrun/app/api/v1/ai.py` | 1091 |
| `batch_generate_reports` | Function | `backend-cloudrun/app/api/v1/ai.py` | 1285 |
| `get_industry_knowledge` | Function | `backend-cloudrun/app/core/prompts.py` | 211 |
| `get_domain_from_device_type` | Function | `backend-cloudrun/app/core/prompts.py` | 454 |
| `get_domain_from_pollutant_code` | Function | `backend-cloudrun/app/core/prompts.py` | 470 |
| `get_domain_knowledge` | Function | `backend-cloudrun/app/core/prompts.py` | 487 |
| `get_pollutant_info` | Function | `backend-cloudrun/app/core/prompts.py` | 500 |
| `build_expert_diagnosis_prompt` | Function | `backend-cloudrun/app/core/prompts.py` | 533 |
| `build_chat_system_prompt` | Function | `backend-cloudrun/app/core/prompts.py` | 599 |
| `build_alarm_analysis_prompt` | Function | `backend-cloudrun/app/core/prompts.py` | 627 |
| `build_comprehensive_diagnosis_prompt` | Function | `backend-cloudrun/app/core/prompts.py` | 671 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Batch_generate_reports → _parse_aliases_from_string` | cross_community | 9 |
| `Batch_generate_reports → _merge_continuous_periods` | cross_community | 7 |
| `Get_latest_data → _parse_aliases_from_string` | cross_community | 6 |
| `Get_active_alarms → _parse_aliases_from_string` | cross_community | 6 |
| `Get_latest_data → _parse_aliases_from_string` | cross_community | 6 |
| `Get_device_online_metrics → _parse_aliases_from_string` | cross_community | 6 |
| `Get_device_flow → _parse_aliases_from_string` | cross_community | 6 |
| `Get_device_pollutants → _parse_aliases_from_string` | cross_community | 6 |
| `Get_latest_monitoring_data → _parse_aliases_from_string` | cross_community | 6 |
| `Download_regulator_report → _parse_json_list` | intra_community | 6 |

## Connected Areas

| Area | Connections |
|------|-------------|
| V1 | 26 calls |
| Openapi | 5 calls |
| Llm | 5 calls |
| Ai | 1 calls |
| Db | 1 calls |
| Scripts | 1 calls |

## How to Explore

1. `gitnexus_context({name: "get_regulator_overview"})` — see callers and callees
2. `gitnexus_query({query: "services"})` — find related execution flows
3. Read key files listed above for implementation details
