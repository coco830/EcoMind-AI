"""Tests for SM4 encryption."""

import pytest

from app.core.encryption import SM4Cipher, get_sm4_cipher


class TestSM4Cipher:
    """Test cases for SM4 encryption."""

    def setup_method(self) -> None:
        """Setup cipher instance."""
        # Use a fixed test key
        self.cipher = SM4Cipher("0123456789abcdef0123456789abcdef")

    def test_encrypt_decrypt(self) -> None:
        """Test encryption and decryption."""
        plaintext = b"Hello, SM4 encryption!"
        ciphertext = self.cipher.encrypt(plaintext)
        decrypted = self.cipher.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_encrypt_decrypt_hex(self) -> None:
        """Test hex encryption and decryption."""
        plaintext = "Test message for SM4"
        ciphertext_hex = self.cipher.encrypt_hex(plaintext)
        decrypted = self.cipher.decrypt_hex(ciphertext_hex)

        assert decrypted == plaintext

    def test_encrypt_different_outputs(self) -> None:
        """Test that same plaintext with different padding produces different cipher blocks."""
        plaintext1 = b"short"
        plaintext2 = b"short text"

        cipher1 = self.cipher.encrypt(plaintext1)
        cipher2 = self.cipher.encrypt(plaintext2)

        assert cipher1 != cipher2

    def test_invalid_key_length(self) -> None:
        """Test that invalid key length raises error."""
        with pytest.raises(ValueError, match="16 bytes"):
            SM4Cipher("short")

    def test_empty_message(self) -> None:
        """Test encrypting empty message."""
        plaintext = b""
        ciphertext = self.cipher.encrypt(plaintext)
        decrypted = self.cipher.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_long_message(self) -> None:
        """Test encrypting long message."""
        plaintext = b"A" * 1000
        ciphertext = self.cipher.encrypt(plaintext)
        decrypted = self.cipher.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_unicode_message(self) -> None:
        """Test encrypting unicode message."""
        plaintext = "中文测试消息 - Chinese test message"
        ciphertext_hex = self.cipher.encrypt_hex(plaintext)
        decrypted = self.cipher.decrypt_hex(ciphertext_hex)

        assert decrypted == plaintext


def test_get_sm4_cipher() -> None:
    """Test global cipher singleton."""
    cipher1 = get_sm4_cipher()
    cipher2 = get_sm4_cipher()

    assert cipher1 is cipher2
