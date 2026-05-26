---
name: protocols
description: "Skill for the Protocols area of EcoMind-AI. 15 symbols across 2 files."
---

# Protocols

15 symbols | 2 files | Cohesion: 93%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how calculate_crc16, crc16_to_hex, verify_crc work
- Modifying protocols-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/protocols/parser.py` | parse, _validate_packet_structure, _parse_data_segment, _detect_version, _extract_cp_content (+6) |
| `backend-cloudrun/app/protocols/crc.py` | calculate_crc16, crc16_to_hex, verify_crc, append_crc |

## Entry Points

Start here when exploring this area:

- **`calculate_crc16`** (Function) — `backend-cloudrun/app/protocols/crc.py:11`
- **`crc16_to_hex`** (Function) — `backend-cloudrun/app/protocols/crc.py:34`
- **`verify_crc`** (Function) — `backend-cloudrun/app/protocols/crc.py:48`
- **`append_crc`** (Function) — `backend-cloudrun/app/protocols/crc.py:67`
- **`parse`** (Method) — `backend-cloudrun/app/protocols/parser.py:49`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `calculate_crc16` | Function | `backend-cloudrun/app/protocols/crc.py` | 11 |
| `crc16_to_hex` | Function | `backend-cloudrun/app/protocols/crc.py` | 34 |
| `verify_crc` | Function | `backend-cloudrun/app/protocols/crc.py` | 48 |
| `append_crc` | Function | `backend-cloudrun/app/protocols/crc.py` | 67 |
| `parse` | Method | `backend-cloudrun/app/protocols/parser.py` | 49 |
| `format_response` | Method | `backend-cloudrun/app/protocols/parser.py` | 426 |
| `_validate_packet_structure` | Method | `backend-cloudrun/app/protocols/parser.py` | 153 |
| `_parse_data_segment` | Method | `backend-cloudrun/app/protocols/parser.py` | 190 |
| `_detect_version` | Method | `backend-cloudrun/app/protocols/parser.py` | 240 |
| `_extract_cp_content` | Method | `backend-cloudrun/app/protocols/parser.py` | 260 |
| `_is_encrypted` | Method | `backend-cloudrun/app/protocols/parser.py` | 273 |
| `_decrypt_sm4` | Method | `backend-cloudrun/app/protocols/parser.py` | 301 |
| `_parse_cp_parameters` | Method | `backend-cloudrun/app/protocols/parser.py` | 331 |
| `_extract_system_time` | Method | `backend-cloudrun/app/protocols/parser.py` | 388 |
| `_validate_timestamp` | Method | `backend-cloudrun/app/protocols/parser.py` | 412 |

## How to Explore

1. `gitnexus_context({name: "calculate_crc16"})` — see callers and callees
2. `gitnexus_query({query: "protocols"})` — find related execution flows
3. Read key files listed above for implementation details
