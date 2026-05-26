---
name: gateway
description: "Skill for the Gateway area of EcoMind-AI. 32 symbols across 8 files."
---

# Gateway

32 symbols | 8 files | Cohesion: 90%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how receive_hj212_data, get_device_registry, inject_demo_data work
- Modifying gateway-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/gateway/server.py` | handle_client, process_message, store_data, _get_device_by_mn, send_ack (+4) |
| `backend-cloudrun/app/gateway/tcp_server.py` | __init__, update_heartbeat, _handle_connection, _process_data, _authenticate_device (+2) |
| `backend-cloudrun/app/gateway/device_registry.py` | _is_cache_valid, get_device_by_mn, get_cache_stats, get_device_registry, close (+1) |
| `backend-cloudrun/app/gateway/hj212_parser.py` | parse, _parse_cp, _verify_crc, _calculate_crc, build_response |
| `backend-cloudrun/app/api/v1/gateway.py` | receive_hj212_data, _update_device_heartbeat |
| `backend-cloudrun/app/api/v1/dashboard.py` | inject_demo_data |
| `backend-cloudrun/app/services/monitoring_service.py` | insert_batch_monitoring_data |
| `backend-cloudrun/app/core/encryption.py` | get_sm4_cipher |

## Entry Points

Start here when exploring this area:

- **`receive_hj212_data`** (Function) — `backend-cloudrun/app/api/v1/gateway.py:57`
- **`get_device_registry`** (Function) — `backend-cloudrun/app/gateway/device_registry.py:144`
- **`inject_demo_data`** (Function) — `backend-cloudrun/app/api/v1/dashboard.py:443`
- **`get_sm4_cipher`** (Function) — `backend-cloudrun/app/core/encryption.py:246`
- **`get_tcp_server`** (Function) — `backend-cloudrun/app/gateway/server.py:348`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `receive_hj212_data` | Function | `backend-cloudrun/app/api/v1/gateway.py` | 57 |
| `get_device_registry` | Function | `backend-cloudrun/app/gateway/device_registry.py` | 144 |
| `inject_demo_data` | Function | `backend-cloudrun/app/api/v1/dashboard.py` | 443 |
| `get_sm4_cipher` | Function | `backend-cloudrun/app/core/encryption.py` | 246 |
| `get_tcp_server` | Function | `backend-cloudrun/app/gateway/server.py` | 348 |
| `run_tcp_server` | Function | `backend-cloudrun/app/gateway/server.py` | 358 |
| `close_device_registry` | Function | `backend-cloudrun/app/gateway/device_registry.py` | 152 |
| `get_device_by_mn` | Method | `backend-cloudrun/app/gateway/device_registry.py` | 60 |
| `get_cache_stats` | Method | `backend-cloudrun/app/gateway/device_registry.py` | 127 |
| `parse` | Method | `backend-cloudrun/app/gateway/hj212_parser.py` | 84 |
| `build_response` | Method | `backend-cloudrun/app/gateway/hj212_parser.py` | 210 |
| `handle_client` | Method | `backend-cloudrun/app/gateway/server.py` | 118 |
| `process_message` | Method | `backend-cloudrun/app/gateway/server.py` | 177 |
| `store_data` | Method | `backend-cloudrun/app/gateway/server.py` | 218 |
| `send_ack` | Method | `backend-cloudrun/app/gateway/server.py` | 317 |
| `insert_batch_monitoring_data` | Method | `backend-cloudrun/app/services/monitoring_service.py` | 85 |
| `update_heartbeat` | Method | `backend-cloudrun/app/gateway/tcp_server.py` | 51 |
| `start` | Method | `backend-cloudrun/app/gateway/server.py` | 73 |
| `stop` | Method | `backend-cloudrun/app/gateway/server.py` | 97 |
| `close` | Method | `backend-cloudrun/app/gateway/device_registry.py` | 52 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Inject_demo_data → _parse_aliases_from_string` | cross_community | 6 |
| `Store_data → _get_session` | cross_community | 4 |
| `Store_data → _find_active_alarm` | cross_community | 4 |
| `Store_data → _update_active_alarm` | cross_community | 4 |
| `Store_data → _get_device_with_org` | cross_community | 4 |
| `Receive_hj212_data → _parse_cp` | intra_community | 3 |
| `Receive_hj212_data → _is_cache_valid` | intra_community | 3 |
| `Receive_hj212_data → _calculate_crc` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Openapi | 3 calls |
| Services | 3 calls |

## How to Explore

1. `gitnexus_context({name: "receive_hj212_data"})` — see callers and callees
2. `gitnexus_query({query: "gateway"})` — find related execution flows
3. Read key files listed above for implementation details
