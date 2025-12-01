#!/usr/bin/env python3
"""Encryption Migration Tool - Migrate ECB encrypted data to CBC format.

This script helps migrate existing ECB-encrypted data to the more secure CBC format.
It should be run once during the upgrade process.

Usage:
    # Dry run (analyze without changes)
    python scripts/migrate_encryption.py --dry-run

    # Perform migration
    python scripts/migrate_encryption.py --execute

    # Migrate with specific key
    SM4_KEY=your_key_here python scripts/migrate_encryption.py --execute

Security Notes:
    - Always backup your database before running migration
    - Run with --dry-run first to see what will be migrated
    - This script is idempotent - CBC data will be skipped
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.encryption import SM4Cipher, EncryptionMode, get_sm4_cipher


def demonstrate_migration():
    """Demonstrate the migration process with sample data."""
    print("\n" + "=" * 60)
    print("SM4 Encryption Migration Demo")
    print("=" * 60)

    cipher = get_sm4_cipher()

    # Sample data
    test_data = [
        "Hello, EcoMind!",
        "HJ 212 Protocol Data: ST=32;CN=2011;PW=123456",
        "敏感环境监测数据 - 2024",
        '{"device_id": "MN001", "value": 123.45}',
    ]

    print("\n1. Creating ECB encrypted data (legacy format):")
    print("-" * 40)

    ecb_samples = []
    for text in test_data:
        ecb_encrypted = cipher.encrypt(text.encode("utf-8"), mode=EncryptionMode.ECB)
        ecb_samples.append((text, ecb_encrypted))
        print(f"  Text: {text[:30]}...")
        print(f"  ECB:  {ecb_encrypted.hex()[:40]}...")
        print(f"  Is CBC format: {cipher.is_cbc_format(ecb_encrypted)}")
        print()

    print("\n2. Migrating to CBC format:")
    print("-" * 40)

    cbc_samples = []
    for text, ecb_data in ecb_samples:
        # Migrate ECB to CBC
        cbc_encrypted = cipher.migrate_ecb_to_cbc(ecb_data)
        cbc_samples.append((text, cbc_encrypted))
        print(f"  Original: {text[:30]}...")
        print(f"  CBC:      {cbc_encrypted.hex()[:40]}...")
        print(f"  Is CBC format: {cipher.is_cbc_format(cbc_encrypted)}")
        print()

    print("\n3. Verifying decryption works for both formats:")
    print("-" * 40)

    for i, (text, ecb_data) in enumerate(ecb_samples):
        cbc_data = cbc_samples[i][1]

        # Decrypt both formats
        ecb_decrypted = cipher.decrypt(ecb_data).decode("utf-8")
        cbc_decrypted = cipher.decrypt(cbc_data).decode("utf-8")

        assert ecb_decrypted == text, "ECB decryption failed"
        assert cbc_decrypted == text, "CBC decryption failed"

        print(f"  ✓ '{text[:30]}...' - Both formats decrypt correctly")

    print("\n4. Security comparison:")
    print("-" * 40)

    # Demonstrate ECB weakness
    repeated_text = "AAAAAAAAAAAAAAAA" * 3  # 48 'A's = 3 blocks
    ecb_repeated = cipher.encrypt(repeated_text.encode("utf-8"), mode=EncryptionMode.ECB)
    cbc_repeated = cipher.encrypt(repeated_text.encode("utf-8"), mode=EncryptionMode.CBC)

    print(f"  Same text repeated 3 times:")
    print(f"  ECB blocks: {ecb_repeated.hex()}")
    print(f"    - Notice: ECB blocks 1-3 are IDENTICAL (insecure!)")
    print(f"  CBC result: {cbc_repeated.hex()[:80]}...")
    print(f"    - Notice: CBC output is completely different (secure)")

    # Show ECB block repetition
    block_size = 16
    ecb_blocks = [ecb_repeated[i:i+block_size].hex() for i in range(0, len(ecb_repeated), block_size)]
    print(f"\n  ECB block analysis:")
    for i, block in enumerate(ecb_blocks):
        print(f"    Block {i+1}: {block}")

    print("\n" + "=" * 60)
    print("Migration demo complete!")
    print("=" * 60)


def analyze_hex_data(hex_data: str) -> dict:
    """Analyze hex-encoded encrypted data."""
    cipher = get_sm4_cipher()
    try:
        data = bytes.fromhex(hex_data)
        is_cbc = cipher.is_cbc_format(data)

        result = {
            "length": len(data),
            "is_cbc_format": is_cbc,
            "format": "CBC (secure)" if is_cbc else "ECB (legacy)",
        }

        # Try to decrypt
        try:
            decrypted = cipher.decrypt(data)
            result["can_decrypt"] = True
            result["plaintext_length"] = len(decrypted)
        except Exception as e:
            result["can_decrypt"] = False
            result["error"] = str(e)

        return result
    except Exception as e:
        return {"error": f"Invalid hex data: {e}"}


def migrate_hex_data(hex_data: str) -> str | None:
    """Migrate hex-encoded ECB data to CBC format."""
    cipher = get_sm4_cipher()
    try:
        data = bytes.fromhex(hex_data)

        if cipher.is_cbc_format(data):
            print("  Already in CBC format, skipping")
            return None

        # Migrate to CBC
        cbc_data = cipher.migrate_ecb_to_cbc(data)
        return cbc_data.hex().upper()
    except Exception as e:
        print(f"  Migration failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Migrate SM4 encrypted data from ECB to CBC format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run interactive demo
  python scripts/migrate_encryption.py --demo

  # Analyze specific hex data
  python scripts/migrate_encryption.py --analyze "ABC123..."

  # Migrate specific hex data
  python scripts/migrate_encryption.py --migrate "ABC123..."

Security:
  - ECB mode reveals patterns in encrypted data
  - CBC mode with random IV provides semantic security
  - Always backup before migration
        """,
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run interactive demonstration of migration process",
    )
    parser.add_argument(
        "--analyze",
        metavar="HEX",
        help="Analyze hex-encoded encrypted data",
    )
    parser.add_argument(
        "--migrate",
        metavar="HEX",
        help="Migrate hex-encoded ECB data to CBC format",
    )

    args = parser.parse_args()

    if args.demo:
        demonstrate_migration()
    elif args.analyze:
        print("\nAnalyzing encrypted data:")
        result = analyze_hex_data(args.analyze)
        for key, value in result.items():
            print(f"  {key}: {value}")
    elif args.migrate:
        print("\nMigrating encrypted data:")
        result = migrate_hex_data(args.migrate)
        if result:
            print(f"  Migrated (CBC): {result}")
    else:
        parser.print_help()
        print("\n\nQuick start: python scripts/migrate_encryption.py --demo")


if __name__ == "__main__":
    main()
