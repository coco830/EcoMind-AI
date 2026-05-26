---
name: ai
description: "Skill for the Ai area of EcoMind-AI. 19 symbols across 4 files."
---

# Ai

19 symbols | 4 files | Cohesion: 84%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how predict_trend, predict_device_trend, analyze_device work
- Modifying ai-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/ai/anomaly_detection.py` | _prepare_features, _detect_constant_values, _detect_spikes, detect_anomalies, get_detector (+3) |
| `backend-cloudrun/app/ai/prediction.py` | _prepare_dataframe, _simple_average_fallback, predict, _predict_with_prophet, _predict_with_neuralprophet (+2) |
| `backend-cloudrun/app/api/v1/ai.py` | predict_device_trend, analyze_device, test_detection |
| `backend-cloudrun/app/api/openapi/ai_tools.py` | _run_prediction |

## Entry Points

Start here when exploring this area:

- **`predict_trend`** (Function) — `backend-cloudrun/app/ai/prediction.py:525`
- **`predict_device_trend`** (Function) — `backend-cloudrun/app/api/v1/ai.py:246`
- **`analyze_device`** (Function) — `backend-cloudrun/app/api/v1/ai.py:102`
- **`test_detection`** (Function) — `backend-cloudrun/app/api/v1/ai.py:151`
- **`get_detector`** (Function) — `backend-cloudrun/app/ai/anomaly_detection.py:330`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `predict_trend` | Function | `backend-cloudrun/app/ai/prediction.py` | 525 |
| `predict_device_trend` | Function | `backend-cloudrun/app/api/v1/ai.py` | 246 |
| `analyze_device` | Function | `backend-cloudrun/app/api/v1/ai.py` | 102 |
| `test_detection` | Function | `backend-cloudrun/app/api/v1/ai.py` | 151 |
| `get_detector` | Function | `backend-cloudrun/app/ai/anomaly_detection.py` | 330 |
| `detect_anomalies` | Function | `backend-cloudrun/app/ai/anomaly_detection.py` | 433 |
| `predict` | Method | `backend-cloudrun/app/ai/prediction.py` | 241 |
| `detect_anomalies` | Method | `backend-cloudrun/app/ai/anomaly_detection.py` | 216 |
| `_run_prediction` | Function | `backend-cloudrun/app/api/openapi/ai_tools.py` | 98 |
| `_get_device_by_mn` | Function | `backend-cloudrun/app/ai/anomaly_detection.py` | 338 |
| `_create_alarms_for_anomalies` | Function | `backend-cloudrun/app/ai/anomaly_detection.py` | 358 |
| `_prepare_dataframe` | Method | `backend-cloudrun/app/ai/prediction.py` | 111 |
| `_simple_average_fallback` | Method | `backend-cloudrun/app/ai/prediction.py` | 146 |
| `_predict_with_prophet` | Method | `backend-cloudrun/app/ai/prediction.py` | 299 |
| `_predict_with_neuralprophet` | Method | `backend-cloudrun/app/ai/prediction.py` | 384 |
| `_validate_predictions` | Method | `backend-cloudrun/app/ai/prediction.py` | 473 |
| `_prepare_features` | Method | `backend-cloudrun/app/ai/anomaly_detection.py` | 94 |
| `_detect_constant_values` | Method | `backend-cloudrun/app/ai/anomaly_detection.py` | 143 |
| `_detect_spikes` | Method | `backend-cloudrun/app/ai/anomaly_detection.py` | 188 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Detect_anomalies → _parse_aliases_from_string` | cross_community | 6 |
| `Predict_device_trend → _parse_aliases_from_string` | cross_community | 6 |
| `Predict_device_trend → _add` | cross_community | 5 |
| `Predict_device_trend → _validate_predictions` | intra_community | 5 |
| `Predict_device_trend → _simple_average_fallback` | intra_community | 5 |
| `Detect_anomalies → _add` | cross_community | 4 |
| `Predict_trend_adaptive → _validate_predictions` | cross_community | 4 |
| `Predict_trend_adaptive → _simple_average_fallback` | cross_community | 4 |
| `Predict_device_trend → _prepare_dataframe` | intra_community | 4 |
| `Detect_anomalies → _detect_constant_values` | cross_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| V1 | 4 calls |
| Services | 1 calls |

## How to Explore

1. `gitnexus_context({name: "predict_trend"})` — see callers and callees
2. `gitnexus_query({query: "ai"})` — find related execution flows
3. Read key files listed above for implementation details
