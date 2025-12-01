"""Tests for SM4 encryption module.

Tests cover:
- CBC mode encryption/decryption (default, secure)
- Legacy ECB mode backward compatibility
- ECB to CBC migration
- Key validation
- Error handling
- Security properties
"""

import os
import pytest

from app.core.encryption import (
    SM4Cipher,
    EncryptionMode,
    get_sm4_cipher,
    reset_cipher,
    _MAGIC_HEADER,
)


# Test key (32 hex chars = 16 bytes)
TEST_KEY = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def cipher():
    """Create a test cipher instance."""
    return SM4Cipher(TEST_KEY)


@pytest.fixture(autouse=True)
def reset_global_cipher():
    """Reset global cipher before each test."""
    reset_cipher()
    yield
    reset_cipher()


class TestSM4CipherBasics:
    """Test basic encryption/decryption functionality."""

    def test_encrypt_decrypt_cbc(self, cipher: SM4Cipher):
        """Test CBC mode encryption and decryption."""
        plaintext = b"Hello, EcoMind!"
        ciphertext = cipher.encrypt(plaintext, mode=EncryptionMode.CBC)
        decrypted = cipher.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_decrypt_ecb_legacy(self, cipher: SM4Cipher):
        """Test ECB mode encryption and decryption (legacy support)."""
        plaintext = b"Legacy data"
        ciphertext = cipher.encrypt(plaintext, mode=EncryptionMode.ECB)
        decrypted = cipher.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_cbc_is_default_mode(self, cipher: SM4Cipher):
        """Test that CBC is the default encryption mode."""
        plaintext = b"Test data"
        ciphertext = cipher.encrypt(plaintext)  # No mode specified
        assert cipher.is_cbc_format(ciphertext)

    def test_encrypt_hex_decrypt_hex(self, cipher: SM4Cipher):
        """Test hex string encryption/decryption."""
        plaintext = "中文测试数据"
        encrypted_hex = cipher.encrypt_hex(plaintext)
        decrypted = cipher.decrypt_hex(encrypted_hex)
        assert decrypted == plaintext

    def test_different_plaintexts(self, cipher: SM4Cipher):
        """Test encryption of various plaintext types."""
        test_cases = [
            b"A",  # Single byte
            b"A" * 16,  # Exactly one block
            b"A" * 32,  # Two blocks
            b"A" * 47,  # Not aligned
            "HJ 212 Data: ST=32;CN=2011".encode(),
            "敏感环境监测数据".encode(),
            os.urandom(1000),  # Random binary data
        ]

        for plaintext in test_cases:
            ciphertext = cipher.encrypt(plaintext)
            decrypted = cipher.decrypt(ciphertext)
            assert decrypted == plaintext, f"Failed for plaintext length {len(plaintext)}"

    def test_empty_message(self, cipher: SM4Cipher):
        """Test encrypting empty message."""
        plaintext = b""
        ciphertext = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(ciphertext)
        assert decrypted == plaintext


class TestCBCFormat:
    """Test CBC format detection and structure."""

    def test_cbc_format_has_magic_header(self, cipher: SM4Cipher):
        """Test that CBC encrypted data has magic header."""
        ciphertext = cipher.encrypt(b"test", mode=EncryptionMode.CBC)
        assert ciphertext[:2] == _MAGIC_HEADER

    def test_ecb_format_no_magic_header(self, cipher: SM4Cipher):
        """Test that ECB encrypted data has no magic header."""
        ciphertext = cipher.encrypt(b"test", mode=EncryptionMode.ECB)
        assert ciphertext[:2] != _MAGIC_HEADER

    def test_is_cbc_format_detection(self, cipher: SM4Cipher):
        """Test format detection."""
        cbc_data = cipher.encrypt(b"test", mode=EncryptionMode.CBC)
        ecb_data = cipher.encrypt(b"test", mode=EncryptionMode.ECB)

        assert cipher.is_cbc_format(cbc_data) is True
        assert cipher.is_cbc_format(ecb_data) is False

    def test_cbc_format_structure(self, cipher: SM4Cipher):
        """Test CBC format: MAGIC(2) + VERSION(1) + MODE(1) + IV(16) + CIPHERTEXT."""
        ciphertext = cipher.encrypt(b"test", mode=EncryptionMode.CBC)

        # Check minimum length: header(4) + IV(16) + at least one block(16) = 36
        assert len(ciphertext) >= 36

        # Check header
        assert ciphertext[:2] == _MAGIC_HEADER
        assert ciphertext[2] == 1  # Version
        assert ciphertext[3] == ord("C")  # Mode = CBC


class TestCBCSecurity:
    """Test CBC mode security properties."""

    def test_cbc_different_iv_each_time(self, cipher: SM4Cipher):
        """Test that CBC uses different IV for each encryption."""
        plaintext = b"Same plaintext"

        ciphertexts = [cipher.encrypt(plaintext) for _ in range(10)]

        # All ciphertexts should be different due to random IV
        unique_ciphertexts = set(ct.hex() for ct in ciphertexts)
        assert len(unique_ciphertexts) == 10

    def test_ecb_same_plaintext_same_ciphertext(self, cipher: SM4Cipher):
        """Test ECB weakness: same plaintext produces same ciphertext."""
        plaintext = b"A" * 16  # One block

        ciphertexts = [
            cipher.encrypt(plaintext, mode=EncryptionMode.ECB)
            for _ in range(5)
        ]

        # ECB produces identical ciphertext for identical plaintext
        assert len(set(ct.hex() for ct in ciphertexts)) == 1

    def test_ecb_repeated_blocks_visible(self, cipher: SM4Cipher):
        """Test ECB weakness: repeated blocks are visible in ciphertext."""
        # Three identical 16-byte blocks
        plaintext = b"A" * 48

        ciphertext = cipher.encrypt(plaintext, mode=EncryptionMode.ECB)

        # In ECB, all three blocks should be identical
        block1 = ciphertext[0:16]
        block2 = ciphertext[16:32]
        block3 = ciphertext[32:48]

        assert block1 == block2 == block3


class TestMigration:
    """Test ECB to CBC migration functionality."""

    def test_migrate_ecb_to_cbc(self, cipher: SM4Cipher):
        """Test migrating ECB encrypted data to CBC format."""
        plaintext = b"Legacy data to migrate"

        # Create ECB encrypted data
        ecb_data = cipher.encrypt(plaintext, mode=EncryptionMode.ECB)
        assert not cipher.is_cbc_format(ecb_data)

        # Migrate to CBC
        cbc_data = cipher.migrate_ecb_to_cbc(ecb_data)
        assert cipher.is_cbc_format(cbc_data)

        # Verify data integrity
        decrypted = cipher.decrypt(cbc_data)
        assert decrypted == plaintext

    def test_auto_detect_format_on_decrypt(self, cipher: SM4Cipher):
        """Test that decrypt auto-detects ECB vs CBC format."""
        plaintext = b"Test data"

        ecb_data = cipher.encrypt(plaintext, mode=EncryptionMode.ECB)
        cbc_data = cipher.encrypt(plaintext, mode=EncryptionMode.CBC)

        # Both should decrypt correctly
        assert cipher.decrypt(ecb_data) == plaintext
        assert cipher.decrypt(cbc_data) == plaintext


class TestKeyValidation:
    """Test key validation."""

    def test_valid_key(self):
        """Test cipher creation with valid key."""
        cipher = SM4Cipher("abcdef0123456789abcdef0123456789")
        assert cipher is not None

    def test_invalid_key_length_short(self):
        """Test rejection of short key."""
        with pytest.raises(ValueError, match="16 bytes"):
            SM4Cipher("abcd")

    def test_invalid_key_length_long(self):
        """Test rejection of long key."""
        with pytest.raises(ValueError, match="16 bytes"):
            SM4Cipher("abcdef0123456789abcdef0123456789abcd")  # 36 hex chars = 18 bytes

    def test_invalid_key_not_hex(self):
        """Test rejection of non-hex key."""
        with pytest.raises(ValueError, match="hexadecimal"):
            SM4Cipher("ghijklmnopqrstuv0123456789abcdef")


class TestErrorHandling:
    """Test error handling."""

    def test_decrypt_empty_data(self, cipher: SM4Cipher):
        """Test decrypting empty data."""
        with pytest.raises(ValueError, match="too short"):
            cipher.decrypt(b"")

    def test_decrypt_short_data(self, cipher: SM4Cipher):
        """Test decrypting too-short data."""
        with pytest.raises(ValueError, match="too short"):
            cipher.decrypt(b"short")

    def test_decrypt_invalid_ecb_length(self, cipher: SM4Cipher):
        """Test decrypting ECB data with wrong length."""
        # ECB data must be multiple of 16 bytes
        with pytest.raises(ValueError, match="not multiple of 16"):
            cipher.decrypt(b"A" * 17)

    def test_decrypt_invalid_cbc_header(self, cipher: SM4Cipher):
        """Test decrypting CBC data with invalid header."""
        # Create fake CBC header with wrong version
        fake_data = _MAGIC_HEADER + bytes([99, ord("C")]) + b"A" * 32
        with pytest.raises(ValueError, match="version"):
            cipher.decrypt(fake_data)


class TestGlobalCipher:
    """Test global cipher instance management."""

    def test_get_sm4_cipher_returns_instance(self):
        """Test getting global cipher instance."""
        cipher = get_sm4_cipher()
        assert isinstance(cipher, SM4Cipher)

    def test_get_sm4_cipher_is_singleton(self):
        """Test that global cipher is singleton."""
        cipher1 = get_sm4_cipher()
        cipher2 = get_sm4_cipher()
        assert cipher1 is cipher2

    def test_reset_cipher_clears_instance(self):
        """Test resetting global cipher."""
        cipher1 = get_sm4_cipher()
        reset_cipher()
        cipher2 = get_sm4_cipher()
        assert cipher1 is not cipher2
