"""
CRC16 Implementation for HJ212 Protocol

This module implements the CRC16 checksum algorithm used in HJ212 protocol.
According to the specification:
- Polynomial: 0xA001 (ANSI CRC16)
- Initial value: 0xFFFF
- Result: 4-byte hexadecimal string
"""


def calculate_crc16(data: bytes) -> int:
    """
    Calculate CRC16 checksum for the given data.

    Args:
        data: The byte data to calculate CRC for

    Returns:
        The CRC16 checksum as an integer
    """
    crc = 0xFFFF  # Initial value

    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001  # Polynomial
            else:
                crc = crc >> 1

    return crc


def crc16_to_hex(crc: int) -> str:
    """
    Convert CRC16 integer to 4-character hex string.

    Args:
        crc: The CRC16 value as integer

    Returns:
        4-character uppercase hex string
    """
    # Format as 4-character hex string with leading zeros
    return f"{crc:04X}"


def verify_crc(data: bytes, expected_crc: str) -> bool:
    """
    Verify if the CRC of data matches the expected CRC string.

    Args:
        data: The data to verify
        expected_crc: The expected CRC as 4-character hex string

    Returns:
        True if CRC matches, False otherwise
    """
    try:
        expected_value = int(expected_crc, 16)
        calculated_value = calculate_crc16(data)
        return calculated_value == expected_value
    except (ValueError, TypeError):
        return False


def append_crc(data: bytes) -> bytes:
    """
    Calculate and append CRC16 to the data.

    Args:
        data: The original data

    Returns:
        Data with CRC16 appended as 4-character hex string
    """
    crc = calculate_crc16(data)
    crc_hex = crc16_to_hex(crc)
    return data + crc_hex.encode('ascii')


# Test the implementation with known values
if __name__ == "__main__":
    # Example test data
    test_data = b"QN=20240101120000000;ST=31;CN=2011;MN=123456789012345678901234;Flag=5;CP=&&w01001-Rtd=7.5,w01001-Flag=N&&"

    crc = calculate_crc16(test_data)
    crc_hex = crc16_to_hex(crc)

    print(f"Test Data: {test_data.decode('ascii')}")
    print(f"CRC16 (int): {crc}")
    print(f"CRC16 (hex): {crc_hex}")

    # Verify CRC
    is_valid = verify_crc(test_data, crc_hex)
    print(f"CRC Verification: {is_valid}")