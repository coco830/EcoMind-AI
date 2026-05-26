---
name: config
description: "Skill for the Config area of EcoMind-AI. 16 symbols across 3 files."
---

# Config

16 symbols | 3 files | Cohesion: 90%

## When to Use

- Working with code in `frontend/`
- Understanding how normalizePollutantCode, getPollutantName, getPollutantUnit work
- Modifying config-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `frontend/src/config/pollutants.ts` | normalizePollutantCode, getPollutantName, getPollutantUnit, generatePollutantOptions, isHeavyMetal (+5) |
| `frontend/src/config/standardLimits.ts` | normalizeStandardCode, isSpecialStandard, resolveGb16297Limit, getStandardLimit |
| `frontend/src/stores/device.ts` | activePollutantDetails, updateDevicePollutants |

## Entry Points

Start here when exploring this area:

- **`normalizePollutantCode`** (Function) — `frontend/src/config/pollutants.ts:157`
- **`getPollutantName`** (Function) — `frontend/src/config/pollutants.ts:223`
- **`getPollutantUnit`** (Function) — `frontend/src/config/pollutants.ts:231`
- **`generatePollutantOptions`** (Function) — `frontend/src/config/pollutants.ts:264`
- **`isHeavyMetal`** (Function) — `frontend/src/config/pollutants.ts:300`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `normalizePollutantCode` | Function | `frontend/src/config/pollutants.ts` | 157 |
| `getPollutantName` | Function | `frontend/src/config/pollutants.ts` | 223 |
| `getPollutantUnit` | Function | `frontend/src/config/pollutants.ts` | 231 |
| `generatePollutantOptions` | Function | `frontend/src/config/pollutants.ts` | 264 |
| `isHeavyMetal` | Function | `frontend/src/config/pollutants.ts` | 300 |
| `getPollutantColor` | Function | `frontend/src/config/pollutants.ts` | 310 |
| `getPollutantInfo` | Function | `frontend/src/config/pollutants.ts` | 215 |
| `formatPollutantValue` | Function | `frontend/src/config/pollutants.ts` | 239 |
| `activePollutantDetails` | Function | `frontend/src/stores/device.ts` | 35 |
| `updateDevicePollutants` | Function | `frontend/src/stores/device.ts` | 123 |
| `getStandardLimit` | Function | `frontend/src/config/standardLimits.ts` | 207 |
| `getPollutantsByCategory` | Function | `frontend/src/config/pollutants.ts` | 255 |
| `generateGroupedPollutantOptions` | Function | `frontend/src/config/pollutants.ts` | 278 |
| `normalizeStandardCode` | Function | `frontend/src/config/standardLimits.ts` | 162 |
| `isSpecialStandard` | Function | `frontend/src/config/standardLimits.ts` | 173 |
| `resolveGb16297Limit` | Function | `frontend/src/config/standardLimits.ts` | 178 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `LoadDevices → NormalizePollutantCode` | cross_community | 3 |

## How to Explore

1. `gitnexus_context({name: "normalizePollutantCode"})` — see callers and callees
2. `gitnexus_query({query: "config"})` — find related execution flows
3. Read key files listed above for implementation details
