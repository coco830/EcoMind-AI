---
name: cluster-85
description: "Skill for the Cluster_85 area of EcoMind-AI. 10 symbols across 1 files."
---

# Cluster_85

10 symbols | 1 files | Cohesion: 100%

## When to Use

- Working with code in `backend-cloudrun/`
- Understanding how encrypt, decrypt, encrypt_hex work
- Modifying cluster_85-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `backend-cloudrun/app/core/encryption.py` | _create_cipher, _pkcs7_pad, _pkcs7_unpad, encrypt, decrypt (+5) |

## Entry Points

Start here when exploring this area:

- **`encrypt`** (Method) — `backend-cloudrun/app/core/encryption.py:100`
- **`decrypt`** (Method) — `backend-cloudrun/app/core/encryption.py:126`
- **`encrypt_hex`** (Method) — `backend-cloudrun/app/core/encryption.py:186`
- **`decrypt_hex`** (Method) — `backend-cloudrun/app/core/encryption.py:199`
- **`migrate_ecb_to_cbc`** (Method) — `backend-cloudrun/app/core/encryption.py:214`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `encrypt` | Method | `backend-cloudrun/app/core/encryption.py` | 100 |
| `decrypt` | Method | `backend-cloudrun/app/core/encryption.py` | 126 |
| `encrypt_hex` | Method | `backend-cloudrun/app/core/encryption.py` | 186 |
| `decrypt_hex` | Method | `backend-cloudrun/app/core/encryption.py` | 199 |
| `migrate_ecb_to_cbc` | Method | `backend-cloudrun/app/core/encryption.py` | 214 |
| `_create_cipher` | Method | `backend-cloudrun/app/core/encryption.py` | 66 |
| `_pkcs7_pad` | Method | `backend-cloudrun/app/core/encryption.py` | 73 |
| `_pkcs7_unpad` | Method | `backend-cloudrun/app/core/encryption.py` | 79 |
| `_decrypt_cbc_format` | Method | `backend-cloudrun/app/core/encryption.py` | 152 |
| `_decrypt_ecb_legacy` | Method | `backend-cloudrun/app/core/encryption.py` | 177 |

## How to Explore

1. `gitnexus_context({name: "encrypt"})` — see callers and callees
2. `gitnexus_query({query: "cluster_85"})` — find related execution flows
3. Read key files listed above for implementation details
