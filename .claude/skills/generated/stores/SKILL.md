---
name: stores
description: "Skill for the Stores area of EcoMind-AI. 6 symbols across 2 files."
---

# Stores

6 symbols | 2 files | Cohesion: 93%

## When to Use

- Working with code in `frontend/`
- Understanding how parseDevicePollutants, loadDevices, selectDevice work
- Modifying stores-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/stores/device.ts` | parseDevicePollutants, loadDevices, selectDevice, selectDeviceByMn |
| `frontend/src/stores/auth.ts` | logout, fetchUser |

## Entry Points

Start here when exploring this area:

- **`parseDevicePollutants`** (Function) — `frontend/src/stores/device.ts:47`
- **`loadDevices`** (Function) — `frontend/src/stores/device.ts:75`
- **`selectDevice`** (Function) — `frontend/src/stores/device.ts:105`
- **`selectDeviceByMn`** (Function) — `frontend/src/stores/device.ts:115`
- **`logout`** (Function) — `frontend/src/stores/auth.ts:33`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `parseDevicePollutants` | Function | `frontend/src/stores/device.ts` | 47 |
| `loadDevices` | Function | `frontend/src/stores/device.ts` | 75 |
| `selectDevice` | Function | `frontend/src/stores/device.ts` | 105 |
| `selectDeviceByMn` | Function | `frontend/src/stores/device.ts` | 115 |
| `logout` | Function | `frontend/src/stores/auth.ts` | 33 |
| `fetchUser` | Function | `frontend/src/stores/auth.ts` | 40 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `LoadDevices → NormalizePollutantCode` | cross_community | 3 |
| `LoadDevices → ParseDevicePollutants` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Config | 1 calls |

## How to Explore

1. `gitnexus_context({name: "parseDevicePollutants"})` — see callers and callees
2. `gitnexus_query({query: "stores"})` — find related execution flows
3. Read key files listed above for implementation details
