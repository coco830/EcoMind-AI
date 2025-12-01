# SM4 Encryption Migration Guide

## Overview

The EcoMind-AI platform has upgraded its SM4 encryption from **ECB mode** (insecure) to **CBC mode** (secure) as part of the enterprise security hardening effort.

**Version:** 2.0
**Date:** 2025-11-29
**Status:** Production Ready

## Why This Upgrade?

### ECB (Electronic Codebook) Mode Problems

| Issue | Impact |
|-------|--------|
| Identical plaintext → identical ciphertext | Pattern leakage |
| No IV (Initialization Vector) | Replay attacks possible |
| Block independence | Block swapping attacks |
| Deterministic output | Dictionary attacks |

### CBC (Cipher Block Chaining) Mode Benefits

| Feature | Security Benefit |
|---------|-----------------|
| Random IV per encryption | Same data encrypts differently |
| Block chaining | Tampering detection |
| Non-deterministic | Prevents pattern analysis |
| Industry standard | Proven security |

## Data Format Changes

### Old Format (ECB - Legacy):
```
[CIPHERTEXT]
```
- Raw encrypted blocks
- Same plaintext = same ciphertext

### New Format (CBC - Secure):
```
[MAGIC:2][VERSION:1][MODE:1][IV:16][CIPHERTEXT]
```
- `MAGIC`: 0xEC 0x0D (EcoMinD signature)
- `VERSION`: Format version (currently 1)
- `MODE`: 'C' for CBC
- `IV`: 16-byte random initialization vector
- `CIPHERTEXT`: Encrypted data

## Migration Options

### Option 1: Clear Database (Recommended for Dev/Test)

If you only have test data, the simplest approach is to clear the encrypted data:

```bash
# Stop the application
# Clear the database
rm backend/ecomind.db  # For SQLite

# Or for PostgreSQL, drop and recreate the database
# Then restart the application
```

### Option 2: Migration Script (For Production Data)

If you have production data that was encrypted with the old ECB mode, use the following migration approach:

1. **Backup your data first!**

2. **Create a migration script** that:
   - Reads all encrypted fields using the OLD decryption method
   - Re-encrypts them using the NEW encryption method
   - Updates the database records

Example migration code:

```python
"""Migration script from SM4-ECB to SM4-CBC."""
import os
from gmssl.sm4 import CryptSM4, SM4_DECRYPT, SM4_ENCRYPT

def decrypt_ecb_legacy(key_bytes: bytes, ciphertext: bytes) -> bytes:
    """Decrypt using the old ECB mode."""
    decryptor = CryptSM4()
    decryptor.set_key(key_bytes, SM4_DECRYPT)
    decrypted = decryptor.crypt_ecb(ciphertext)
    pad_len = decrypted[-1]
    return decrypted[:-pad_len]

def encrypt_cbc_new(key_bytes: bytes, plaintext: bytes) -> bytes:
    """Encrypt using the new CBC mode."""
    iv = os.urandom(16)
    pad_len = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad_len] * pad_len)
    encryptor = CryptSM4()
    encryptor.set_key(key_bytes, SM4_ENCRYPT)
    ciphertext = encryptor.crypt_cbc(iv, padded)
    return iv + ciphertext

def migrate_encrypted_field(key_hex: str, old_ciphertext_hex: str) -> str:
    """Migrate a single encrypted field from ECB to CBC."""
    key_bytes = bytes.fromhex(key_hex)
    old_ciphertext = bytes.fromhex(old_ciphertext_hex)

    # Decrypt with old ECB method
    plaintext = decrypt_ecb_legacy(key_bytes, old_ciphertext)

    # Re-encrypt with new CBC method
    new_ciphertext = encrypt_cbc_new(key_bytes, plaintext)

    return new_ciphertext.hex().upper()
```

### Option 3: Dual-Mode Support (Temporary)

For a gradual migration, you could temporarily support both modes:

```python
def decrypt_auto_detect(key_bytes: bytes, ciphertext: bytes) -> bytes:
    """Try CBC first, fall back to ECB for legacy data."""
    try:
        # Try CBC (new format)
        return decrypt_cbc(key_bytes, ciphertext)
    except Exception:
        # Fall back to ECB (legacy)
        return decrypt_ecb_legacy(key_bytes, ciphertext)
```

**Warning:** This approach should only be temporary. Set a deadline to complete the migration and remove ECB support.

## Verification

After migration, verify that:

1. All encrypted data can be decrypted successfully
2. New encryption produces different ciphertext each time (due to random IV)
3. Application functionality works correctly

```python
# Verification test
from app.core.encryption import SM4Cipher

cipher = SM4Cipher()
test_data = "Hello, World!"

# Encrypt twice - should produce different ciphertexts
encrypted1 = cipher.encrypt_hex(test_data)
encrypted2 = cipher.encrypt_hex(test_data)

assert encrypted1 != encrypted2  # Different due to random IV
assert cipher.decrypt_hex(encrypted1) == test_data
assert cipher.decrypt_hex(encrypted2) == test_data
print("Verification passed!")
```

## Security Recommendations

1. **Generate a new SM4 key** after migration for maximum security
2. **Update .env file** with new credentials: `openssl rand -hex 16`
3. **Audit encrypted data** to ensure nothing was lost in migration
4. **Update documentation** to reflect the new encryption standard

## Questions?

Contact the security team or refer to the project documentation for further assistance.
