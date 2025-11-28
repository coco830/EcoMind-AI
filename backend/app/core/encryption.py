"""SM4 encryption/decryption for HJ 212 protocol data."""

from gmssl.sm4 import CryptSM4, SM4_DECRYPT, SM4_ENCRYPT

from app.core.config import get_settings

settings = get_settings()


class SM4Cipher:
    """SM4 cipher for encrypting/decrypting HJ 212 protocol data."""

    def __init__(self, key: str | None = None) -> None:
        """Initialize SM4 cipher with hex key."""
        key_bytes = bytes.fromhex(key or settings.sm4_key)
        if len(key_bytes) != 16:
            raise ValueError("SM4 key must be 16 bytes (32 hex characters)")
        self._key = key_bytes
        self._encryptor = CryptSM4()
        self._decryptor = CryptSM4()
        self._encryptor.set_key(self._key, SM4_ENCRYPT)
        self._decryptor.set_key(self._key, SM4_DECRYPT)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext using SM4-ECB mode."""
        # Pad to 16-byte boundary using PKCS7
        pad_len = 16 - (len(plaintext) % 16)
        padded = plaintext + bytes([pad_len] * pad_len)
        return self._encryptor.crypt_ecb(padded)

    def decrypt(self, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext using SM4-ECB mode."""
        decrypted = self._decryptor.crypt_ecb(ciphertext)
        # Remove PKCS7 padding
        pad_len = decrypted[-1]
        return decrypted[:-pad_len]

    def encrypt_hex(self, plaintext: str) -> str:
        """Encrypt string and return hex-encoded result."""
        encrypted = self.encrypt(plaintext.encode("utf-8"))
        return encrypted.hex().upper()

    def decrypt_hex(self, ciphertext_hex: str) -> str:
        """Decrypt hex-encoded ciphertext and return string."""
        ciphertext = bytes.fromhex(ciphertext_hex)
        decrypted = self.decrypt(ciphertext)
        return decrypted.decode("utf-8")


# Global cipher instance
_cipher: SM4Cipher | None = None


def get_sm4_cipher() -> SM4Cipher:
    """Get or create global SM4 cipher instance."""
    global _cipher
    if _cipher is None:
        _cipher = SM4Cipher()
    return _cipher
