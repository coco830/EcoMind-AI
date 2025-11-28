#!/usr/bin/env python3
"""
Simple test script for HJ212 Parser without pytest dependency
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.protocols.parser import HJ212Parser
from app.protocols.models import ParserConfig
from app.protocols.enums import ProtocolVersion
from app.protocols.crc import calculate_crc16, crc16_to_hex


def create_test_packet(data_segment: str) -> bytes:
    """Create a valid HJ212 packet with proper CRC"""
    data_len = len(data_segment)
    crc = calculate_crc16(data_segment.encode('ascii'))
    crc_hex = crc16_to_hex(crc)
    packet = f"##{data_len:04d}{data_segment}{crc_hex}\r\n"
    return packet.encode('ascii')


def test_2017_version():
    """Test HJ 212-2017 version packet parsing"""
    print("\n=== Testing HJ 212-2017 Version ===")

    data_segment = (
        "QN=20240101120000000;"
        "ST=31;"
        "CN=2011;"
        "PW=123456;"
        "MN=888888888888888888888888;"
        "Flag=5;"  # Version 1 (2017)
        "CP=&&DataTime=20240101120000;"
        "w01001-Rtd=7.5,w01001-Flag=N;"
        "w01018-Rtd=25.3,w01018-Flag=N;"
        "w21003-Rtd=1.2,w21003-Flag=N&&"
    )

    packet = create_test_packet(data_segment)
    print(f"Packet: {packet.decode('ascii', errors='ignore')[:100]}...")

    parser = HJ212Parser()
    result = parser.parse(packet)

    print(f"✓ Valid: {result.is_valid}")
    print(f"✓ Version: {result.version.name}")
    print(f"✓ Device ID: {result.device_id}")
    print(f"✓ Command: {result.command_type}")
    print(f"✓ System: {result.system_type}")
    print(f"✓ Parameters count: {len(result.parameters)}")

    for code, param in result.parameters.items():
        if code != "DataTime":
            print(f"  - {code}: {param.rtd} (Flag: {param.flag})")

    # Count only actual measurement parameters (exclude DataTime)
    measurement_params = [p for p in result.parameters if p != "DataTime"]

    assert result.is_valid, "Packet should be valid"
    assert result.version == ProtocolVersion.HJ212_2017, "Should detect as 2017 version"
    assert len(measurement_params) == 3, "Should have 3 measurement parameters"

    print("✅ 2017 version test passed!")


def test_2025_version():
    """Test HJ 212-2025 version packet parsing"""
    print("\n=== Testing HJ 212-2025 Version ===")

    data_segment = (
        "QN=20250101080000000;"
        "ST=44;"  # Facility power (2025)
        "CN=2051;"
        "PW=123456;"
        "MN=999999999999999999999999;"
        "Flag=9;"  # Version 2 (2025)
        "CP=&&DataTime=20250101080000;"
        "d10001-Rtd=150.5,d10001-Flag=N;"  # Power parameter
        "d10007-Rtd=10.2,d10007-Flag=N;"
        "p10001-Rtd=8.5,p10001-Flag=N&&"
    )

    packet = create_test_packet(data_segment)
    print(f"Packet: {packet.decode('ascii', errors='ignore')[:100]}...")

    parser = HJ212Parser()
    result = parser.parse(packet)

    print(f"✓ Valid: {result.is_valid}")
    print(f"✓ Version: {result.version.name}")
    print(f"✓ Device ID: {result.device_id}")
    print(f"✓ System: {result.system_type}")
    print(f"✓ Parameters count: {len(result.parameters)}")

    for code, param in result.parameters.items():
        if code != "DataTime":
            print(f"  - {code}: {param.rtd} (2025 specific parameter)")

    assert result.is_valid, "Packet should be valid"
    assert result.version == ProtocolVersion.HJ212_2025, "Should detect as 2025 version"
    assert "d10001" in result.parameters, "Should have power parameters"

    print("✅ 2025 version test passed!")


def test_air_quality_data():
    """Test air quality monitoring data parsing"""
    print("\n=== Testing Air Quality Data ===")

    data_segment = (
        "QN=20240101120000000;"
        "ST=22;"  # Air quality
        "CN=2011;"
        "MN=666666666666666666666666;"
        "Flag=5;"
        "CP=&&DataTime=20240101120000;"
        "a01011-Rtd=15.3,a01011-Flag=N;"
        "a01012-Rtd=120.5,a01012-Flag=N;"
        "a34013-Rtd=25.6,a34013-Flag=N;"
        "a21026-Rtd=85.3,a21026-Flag=N;"
        "a21002-Rtd=120.8,a21002-Flag=N&&"
    )

    packet = create_test_packet(data_segment)
    parser = HJ212Parser()
    result = parser.parse(packet)

    print(f"✓ Valid: {result.is_valid}")
    print(f"✓ System: {result.system_type}")
    print(f"✓ Air quality parameters:")
    print(f"  - 烟气流速: {result.parameters['a01011'].rtd} m/s")
    print(f"  - 烟气温度: {result.parameters['a01012'].rtd} ℃")
    print(f"  - 烟尘颗粒物: {result.parameters['a34013'].rtd} mg/m³")
    print(f"  - SO2: {result.parameters['a21026'].rtd} mg/m³")
    print(f"  - NOx: {result.parameters['a21002'].rtd} mg/m³")

    # Count only actual measurement parameters (exclude DataTime)
    measurement_params = [p for p in result.parameters if p != "DataTime"]

    assert result.system_type == "AIR_QUALITY", "Should be air quality system"
    assert len(measurement_params) == 5, "Should have 5 air parameters"

    print("✅ Air quality test passed!")


def test_split_packet():
    """Test split packet handling"""
    print("\n=== Testing Split Packet ===")

    data_segment = (
        "QN=20240101120000000;"
        "ST=31;"
        "CN=2011;"
        "MN=111111111111111111111111;"
        "Flag=7;"  # Has split bit
        "PNUM=3;"
        "PNO=1;"
        "CP=&&w01001-Rtd=7.5&&"
    )

    packet = create_test_packet(data_segment)
    parser = HJ212Parser()
    result = parser.parse(packet)

    print(f"✓ Valid: {result.is_valid}")
    print(f"✓ Is split: {result.segment.is_split}")
    print(f"✓ Packet number: {result.segment.pno} of {result.segment.pnum}")

    assert result.segment.is_split is True, "Should detect split packet"
    assert result.segment.pnum == 3, "Should have 3 total packets"
    assert result.segment.pno == 1, "Should be packet 1"

    print("✅ Split packet test passed!")


def test_invalid_crc():
    """Test invalid CRC detection"""
    print("\n=== Testing Invalid CRC ===")

    data_segment = "QN=20240101120000000;ST=31;CN=2011;MN=444444444444444444444444;Flag=5;CP=&&&&"

    # Create packet with wrong CRC
    data_len = len(data_segment)
    packet = f"##{data_len:04d}{data_segment}0000\r\n".encode('ascii')

    parser = HJ212Parser(ParserConfig(validate_crc=True, strict_mode=False))
    result = parser.parse(packet)

    print(f"✓ Valid: {result.is_valid}")
    print(f"✓ Errors: {result.errors}")

    assert not result.is_valid, "Should be invalid due to CRC"
    assert any("CRC" in err for err in result.errors), "Should have CRC error"

    print("✅ Invalid CRC test passed!")


def test_version_detection():
    """Test version detection with different flag values"""
    print("\n=== Testing Version Detection ===")

    test_cases = [
        (0, ProtocolVersion.HJ212_2017, "Flag=0"),
        (4, ProtocolVersion.HJ212_2017, "Flag=4 (version bits=1)"),
        (5, ProtocolVersion.HJ212_2017, "Flag=5 (version bits=1, ACK)"),
        (8, ProtocolVersion.HJ212_2025, "Flag=8 (version bits=2)"),
        (12, ProtocolVersion.HJ212_2025, "Flag=12 (version bits=3)"),
    ]

    parser = HJ212Parser()

    for flag_value, expected_version, description in test_cases:
        data_segment = f"QN=20240101120000000;ST=31;CN=2011;MN=888888888888888888888888;Flag={flag_value};CP=&&&&"
        packet = create_test_packet(data_segment)
        result = parser.parse(packet)

        print(f"  {description}: {result.version.name} {'✓' if result.version == expected_version else '✗'}")

        assert result.version == expected_version, f"Flag {flag_value} should be {expected_version.name}"

    print("✅ Version detection test passed!")


def test_response_format():
    """Test response message formatting"""
    print("\n=== Testing Response Format ===")

    data_segment = (
        "QN=20240101120000000;"
        "ST=31;"
        "CN=2011;"
        "PW=123456;"
        "MN=777777777777777777777777;"
        "Flag=5;"
        "CP=&&w01001-Rtd=7.5&&"
    )

    packet = create_test_packet(data_segment)
    parser = HJ212Parser()
    result = parser.parse(packet)

    # Format ACK response
    response = parser.format_response(result)
    print(f"Response: {response.decode('ascii', errors='ignore')[:100]}...")

    # Parse the response to verify
    response_parsed = parser.parse(response)

    print(f"✓ Response valid: {response_parsed.is_valid}")
    print(f"✓ Response command: {response_parsed.segment.cn}")
    print(f"✓ Response MN matches: {response_parsed.segment.mn == result.segment.mn}")

    assert response_parsed.is_valid, "Response should be valid"
    assert response_parsed.segment.cn == "9014", "Should be data ACK command"

    print("✅ Response format test passed!")


def main():
    """Run all tests"""
    print("=" * 60)
    print("HJ212 Protocol Parser Test Suite")
    print("=" * 60)

    tests = [
        test_2017_version,
        test_2025_version,
        test_air_quality_data,
        test_split_packet,
        test_invalid_crc,
        test_version_detection,
        test_response_format,
    ]

    failed = 0
    for test_func in tests:
        try:
            test_func()
        except AssertionError as e:
            print(f"❌ Test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ Test error: {e}")
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())