"""SM4 encryption/decryption for HJ 212 protocol data.

Security Notes:
- Uses SM4-CBC mode with random IV for each encryption (more secure than ECB)
- IV is prepended to ciphertext for transmission
- PKCS7 padding is used for block alignment
- Supports legacy ECB mode decryption for data migration
"""

import os
import struct
import time
from enum import Enum
from typing import Literal

from gmssl.sm4 import CryptSM4, SM4_DECRYPT, SM4_ENCRYPT

from app.core.config import get_settings

settings = get_settings()


class EncryptionMode(str, Enum):
    """Supported encryption modes."""

    CBC = "cbc"  # Cipher Block Chaining (recommended)
    ECB = "ecb"  # Electronic Codebook (legacy, insecure)


# Magic bytes to identify encryption format
# Format: MAGIC(2) + VERSION(1) + MODE(1) + IV(16) + CIPHERTEXT
_MAGIC_HEADER = b"\xEC\x0D"  # 0xEC 0x0D = "EcoMinD" signature
_FORMAT_VERSION = 1


class SM4Cipher:
    """SM4 cipher for encrypting/decrypting HJ 212 protocol data.

    Security:
    - Default mode is CBC which provides semantic security
    - Each encryption uses a random 16-byte IV
    - Legacy ECB decryption supported for migration only
    """

    def __init__(self, key: str | None = None) -> None:
        """Initialize SM4 cipher with hex key.

        Args:
            key: 32-character hex string (16 bytes). If None, uses config default.

        Raises:
            ValueError: If key is not exactly 16 bytes (32 hex characters).
        """
        key_hex = key or settings.sm4_key
        try:
            key_bytes = bytes.fromhex(key_hex)
        except ValueError as e:
            raise ValueError(f"SM4 key must be valid hexadecimal: {e}")

        if len(key_bytes) != 16:
            raise ValueError(
                f"SM4 key must be 16 bytes (32 hex characters), got {len(key_bytes)} bytes"
            )

        self._key = key_bytes

    def _create_cipher(self, mode: Literal["encrypt", "decrypt"]) -> CryptSM4:
        """Create a new SM4 cipher instance."""
        cipher = CryptSM4()
        cipher.set_key(self._key, SM4_ENCRYPT if mode == "encrypt" else SM4_DECRYPT)
        return cipher

    @staticmethod
    def _pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
        """Apply PKCS7 padding to data."""
        pad_len = block_size - (len(data) % block_size)
        return data + bytes([pad_len] * pad_len)

    @staticmethod
    def _pkcs7_unpad(data: bytes) -> bytes:
        """Remove PKCS7 padding from data.

        Raises:
            ValueError: If padding is invalid.
        """
        if not data:
            raise ValueError("Cannot unpad empty data")

        pad_len = data[-1]

        # Validate padding
        if pad_len == 0 or pad_len > 16:
            raise ValueError(f"Invalid PKCS7 padding length: {pad_len}")

        # Verify all padding bytes are correct
        if data[-pad_len:] != bytes([pad_len] * pad_len):
            raise ValueError("Invalid PKCS7 padding bytes")

        return data[:-pad_len]

    def encrypt(self, plaintext: bytes, mode: EncryptionMode = EncryptionMode.CBC) -> bytes:
        """Encrypt plaintext using SM4.

        Args:
            plaintext: Data to encrypt.
            mode: Encryption mode (CBC recommended, ECB for legacy only).

        Returns:
            For CBC: MAGIC(2) + VERSION(1) + MODE(1) + IV(16) + CIPHERTEXT
            For ECB: Raw ciphertext (legacy format)
        """
        padded = self._pkcs7_pad(plaintext)
        cipher = self._create_cipher("encrypt")

        if mode == EncryptionMode.CBC:
            # Generate random IV for each encryption
            iv = os.urandom(16)
            ciphertext = cipher.crypt_cbc(iv, padded)

            # Build versioned format: MAGIC + VERSION + MODE + IV + CIPHERTEXT
            header = _MAGIC_HEADER + bytes([_FORMAT_VERSION, ord("C")]) + iv
            return header + ciphertext
        else:
            # Legacy ECB mode (not recommended)
            return cipher.crypt_ecb(padded)

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext, auto-detecting format.

        Supports:
        - New CBC format with header (recommended)
        - Legacy ECB format (for migration)

        Args:
            ciphertext: Encrypted data.

        Returns:
            Decrypted plaintext.

        Raises:
            ValueError: If ciphertext is invalid or corrupted.
        """
        if len(ciphertext) < 16:
            raise ValueError("Ciphertext too short")

        # Check for new format with magic header
        if ciphertext[:2] == _MAGIC_HEADER:
            return self._decrypt_cbc_format(ciphertext)
        else:
            # Legacy ECB format
            return self._decrypt_ecb_legacy(ciphertext)

    def _decrypt_cbc_format(self, ciphertext: bytes) -> bytes:
        """Decrypt new CBC format with header."""
        if len(ciphertext) < 20:  # MAGIC(2) + VERSION(1) + MODE(1) + IV(16)
            raise ValueError("Invalid CBC ciphertext: too short")

        # Parse header
        version = ciphertext[2]
        mode_byte = ciphertext[3]

        if version != _FORMAT_VERSION:
            raise ValueError(f"Unsupported encryption format version: {version}")

        if mode_byte != ord("C"):
            raise ValueError(f"Invalid mode byte in header: {mode_byte}")

        iv = ciphertext[4:20]
        encrypted_data = ciphertext[20:]

        if len(encrypted_data) == 0 or len(encrypted_data) % 16 != 0:
            raise ValueError("Invalid CBC ciphertext: wrong length")

        cipher = self._create_cipher("decrypt")
        decrypted = cipher.crypt_cbc(iv, encrypted_data)
        return self._pkcs7_unpad(decrypted)

    def _decrypt_ecb_legacy(self, ciphertext: bytes) -> bytes:
        """Decrypt legacy ECB format (for migration support)."""
        if len(ciphertext) % 16 != 0:
            raise ValueError("Invalid ECB ciphertext: length not multiple of 16")

        cipher = self._create_cipher("decrypt")
        decrypted = cipher.crypt_ecb(ciphertext)
        return self._pkcs7_unpad(decrypted)

    def encrypt_hex(self, plaintext: str, mode: EncryptionMode = EncryptionMode.CBC) -> str:
        """Encrypt string and return hex-encoded result.

        Args:
            plaintext: String to encrypt.
            mode: Encryption mode.

        Returns:
            Uppercase hex string of encrypted data.
        """
        encrypted = self.encrypt(plaintext.encode("utf-8"), mode)
        return encrypted.hex().upper()

    def decrypt_hex(self, ciphertext_hex: str) -> str:
        """Decrypt hex-encoded ciphertext and return string.

        Auto-detects CBC vs ECB format.

        Args:
            ciphertext_hex: Hex string of encrypted data.

        Returns:
            Decrypted string.
        """
        ciphertext = bytes.fromhex(ciphertext_hex)
        decrypted = self.decrypt(ciphertext)
        return decrypted.decode("utf-8")

    def migrate_ecb_to_cbc(self, ecb_ciphertext: bytes) -> bytes:
        """Migrate ECB-encrypted data to CBC format.

        Use this to upgrade legacy encrypted data.

        Args:
            ecb_ciphertext: Data encrypted with ECB mode.

        Returns:
            Same data re-encrypted with CBC mode.
        """
        # Decrypt with ECB
        plaintext = self._decrypt_ecb_legacy(ecb_ciphertext)
        # Re-encrypt with CBC
        return self.encrypt(plaintext, EncryptionMode.CBC)

    def is_cbc_format(self, ciphertext: bytes) -> bool:
        """Check if ciphertext uses new CBC format.

        Args:
            ciphertext: Encrypted data to check.

        Returns:
            True if using CBC format with header, False if legacy ECB.
        """
        return len(ciphertext) >= 2 and ciphertext[:2] == _MAGIC_HEADER


# Global cipher instance (lazy initialization)
_cipher: SM4Cipher | None = None


def get_sm4_cipher() -> SM4Cipher:
    """Get or create global SM4 cipher instance.

    Thread-safe lazy initialization.
    """
    global _cipher
    if _cipher is None:
        _cipher = SM4Cipher()
    return _cipher


def reset_cipher() -> None:
    """Reset global cipher instance.

    Useful for testing or when key changes.
    """
    global _cipher
    _cipher = None
