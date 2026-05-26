---
name: api
description: "Skill for the Api area of EcoMind-AI. 9 symbols across 5 files."
---

# Api

9 symbols | 5 files | Cohesion: 100%

## When to Use

- Working with code in `frontend/`
- Understanding how get_current_user, decode_access_token, get work
- Modifying api-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/api/devices.ts` | get, getStats, getIndustryTypes |
| `frontend/src/api/alarms.ts` | get, getStats |
| `frontend/src/api/selfInspection.ts` | get, getOpsBrief |
| `backend-cloudrun/app/api/deps.py` | get_current_user |
| `backend-cloudrun/app/core/security.py` | decode_access_token |

## Entry Points

Start here when exploring this area:

- **`get_current_user`** (Function) — `backend-cloudrun/app/api/deps.py:50`
- **`decode_access_token`** (Function) — `backend-cloudrun/app/core/security.py:49`
- **`get`** (Method) — `frontend/src/api/devices.ts:233`
- **`getStats`** (Method) — `frontend/src/api/devices.ts:249`
- **`getIndustryTypes`** (Method) — `frontend/src/api/devices.ts:253`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `get_current_user` | Function | `backend-cloudrun/app/api/deps.py` | 50 |
| `decode_access_token` | Function | `backend-cloudrun/app/core/security.py` | 49 |
| `get` | Method | `frontend/src/api/devices.ts` | 233 |
| `getStats` | Method | `frontend/src/api/devices.ts` | 249 |
| `getIndustryTypes` | Method | `frontend/src/api/devices.ts` | 253 |
| `get` | Method | `frontend/src/api/alarms.ts` | 58 |
| `getStats` | Method | `frontend/src/api/alarms.ts` | 78 |
| `get` | Method | `frontend/src/api/selfInspection.ts` | 367 |
| `getOpsBrief` | Method | `frontend/src/api/selfInspection.ts` | 421 |

## How to Explore

1. `gitnexus_context({name: "get_current_user"})` — see callers and callees
2. `gitnexus_query({query: "api"})` — find related execution flows
3. Read key files listed above for implementation details
