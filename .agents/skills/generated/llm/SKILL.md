---
name: llm
description: "Skill for the Llm area of EcoMind-AI. 15 symbols across 2 files."
---

# Llm

15 symbols | 2 files | Cohesion: 91%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how SparkClientError, SparkAuthError, SparkConnectionError work
- Modifying llm-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/services/llm/spark_client.py` | _generate_auth_url, _format_messages, _build_request_payload, _build_http_payload, _build_http_headers (+9) |
| `backend-cloudrun/app/services/scheduler.py` | _call_spark_api |

## Entry Points

Start here when exploring this area:

- **`SparkClientError`** (Class) — `backend-cloudrun/app/services/llm/spark_client.py:29`
- **`SparkAuthError`** (Class) — `backend-cloudrun/app/services/llm/spark_client.py:35`
- **`SparkConnectionError`** (Class) — `backend-cloudrun/app/services/llm/spark_client.py:41`
- **`chat_stream`** (Method) — `backend-cloudrun/app/services/llm/spark_client.py:286`
- **`chat`** (Method) — `backend-cloudrun/app/services/llm/spark_client.py:533`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `SparkClientError` | Class | `backend-cloudrun/app/services/llm/spark_client.py` | 29 |
| `SparkAuthError` | Class | `backend-cloudrun/app/services/llm/spark_client.py` | 35 |
| `SparkConnectionError` | Class | `backend-cloudrun/app/services/llm/spark_client.py` | 41 |
| `chat_stream` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 286 |
| `chat` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 533 |
| `test_connection` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 584 |
| `_call_spark_api` | Function | `backend-cloudrun/app/services/scheduler.py` | 239 |
| `_generate_auth_url` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 134 |
| `_format_messages` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 180 |
| `_build_request_payload` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 198 |
| `_build_http_payload` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 230 |
| `_build_http_headers` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 245 |
| `_extract_http_content` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 258 |
| `_http_chat_stream` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 373 |
| `_stream_response` | Method | `backend-cloudrun/app/services/llm/spark_client.py` | 454 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Generate_ai_report_sync → _format_messages` | cross_community | 4 |
| `Generate_ai_report_sync → _generate_auth_url` | cross_community | 4 |
| `Generate_ai_report_sync → _stream_response` | cross_community | 4 |
| `Chat_stream → _format_messages` | intra_community | 4 |
| `Generate_ai_report_sync → _build_http_headers` | cross_community | 3 |
| `Generate_ai_report_sync → _extract_http_content` | cross_community | 3 |

## How to Explore

1. `gitnexus_context({name: "SparkClientError"})` — see callers and callees
2. `gitnexus_query({query: "llm"})` — find related execution flows
3. Read key files listed above for implementation details
