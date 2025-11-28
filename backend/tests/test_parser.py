"""
Unit tests for HJ212 Protocol Parser

This module tests the HJ212 parser with various protocol message formats
including both HJ 212-2017 and HJ 212-2025 versions.
"""

import pytest
from datetime import datetime

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.protocols.parser import HJ212Parser
from app.protocols.models import ParserConfig, ParsedData
from app.protocols.enums import ProtocolVersion, CommandCode
from app.protocols.crc import calculate_crc16, crc16_to_hex


class TestHJ212Parser:
    """Test cases for HJ212Parser"""

    def setup_method(self):
        """Setup test environment before each test"""
        self.parser = HJ212Parser()

    def create_test_packet(self, data_segment: str, calculate_crc: bool = True) -> bytes:
        """
        Helper method to create a valid HJ212 packet.

        Args:
            data_segment: The data segment content
            calculate_crc: Whether to calculate valid CRC

        Returns:
            Complete packet as bytes
        """
        data_len = len(data_segment)

        if calculate_crc:
            crc = calculate_crc16(data_segment.encode('ascii'))
            crc_hex = crc16_to_hex(crc)
        else:
            crc_hex = "0000"  # Invalid CRC for testing

        packet = f"##{data_len:04d}{data_segment}{crc_hex}\r\n"
        return packet.encode('ascii')

    def test_parse_2017_realtime_data(self):
        """Test parsing HJ 212-2017 real-time data packet"""
        # Create a 2017 version packet (Flag=5, version bits = 1)
        data_segment = (
            "QN=20240101120000000;"
            "ST=31;"
            "CN=2011;"
            "PW=123456;"
            "MN=888888888888888888888888;"
            "Flag=5;"  # Binary: 0000 0101 (version=1, no split, need ack)
            "CP=&&DataTime=20240101120000;"
            "w01001-Rtd=7.5,w01001-Flag=N;"
            "w01018-Rtd=25.3,w01018-Flag=N;"
            "w21003-Rtd=1.2,w21003-Flag=N&&"
        )

        packet = self.create_test_packet(data_segment)
        result = self.parser.parse(packet)

        # Verify basic structure
        assert result.is_valid
        assert result.version == ProtocolVersion.HJ212_2017
        assert not result.is_encrypted

        # Verify segment data
        assert result.segment.mn == "888888888888888888888888"
        assert result.segment.st == "31"
        assert result.segment.cn == "2011"
        assert result.segment.needs_ack is True
        assert result.segment.is_split is False
        assert result.segment.protocol_version == 1

        # Verify parameters
        assert len(result.parameters) == 3
        assert result.parameters["w01001"].rtd == 7.5
        assert result.parameters["w01001"].flag == "N"
        assert result.parameters["w01018"].rtd == 25.3
        assert result.parameters["w21003"].rtd == 1.2

        # Verify system time extraction
        assert result.system_time is not None
        assert result.system_time.year == 2024

    def test_parse_2025_version(self):
        """Test parsing HJ 212-2025 version packet"""
        # Create a 2025 version packet (Flag=9, version bits = 2)
        data_segment = (
            "QN=20250101080000000;"
            "ST=44;"  # Facility power monitoring (2025 specific)
            "CN=2051;"  # Minute data
            "PW=123456;"
            "MN=999999999999999999999999;"
            "Flag=9;"  # Binary: 0000 1001 (version=2, no split, need ack)
            "CP=&&DataTime=20250101080000;"
            "d10001-Rtd=150.5,d10001-Flag=N;"  # Power parameter (2025)
            "d10007-Rtd=10.2,d10007-Flag=N;"    # A-phase current (2025)
            "p10001-Rtd=8.5,p10001-Flag=N&&"    # Fan current (2025)
        )

        packet = self.create_test_packet(data_segment)
        result = self.parser.parse(packet)

        # Verify version detection
        assert result.is_valid
        assert result.version == ProtocolVersion.HJ212_2025
        assert not result.is_encrypted  # Plain text in this example

        # Verify segment data
        assert result.segment.st == "44"  # 2025-specific system code
        assert result.segment.cn == "2051"
        assert result.segment.protocol_version == 2

        # Verify 2025-specific parameters
        assert len(result.parameters) == 3
        assert result.parameters["d10001"].rtd == 150.5  # Total active power
        assert result.parameters["d10007"].rtd == 10.2   # A-phase current
        assert result.parameters["p10001"].rtd == 8.5    # Fan current

    def test_parse_split_packet(self):
        """Test parsing split packet with packet info"""
        # Create a split packet (Flag=7, split bit set)
        data_segment = (
            "QN=20240101120000000;"
            "ST=31;"
            "CN=2011;"
            "MN=111111111111111111111111;"
            "Flag=7;"  # Binary: 0000 0111 (version=1, has split, need ack)
            "PNUM=3;"  # Total 3 packets
            "PNO=1;"   # This is packet 1
            "CP=&&w01001-Rtd=7.5&&"
        )

        packet = self.create_test_packet(data_segment)
        result = self.parser.parse(packet)

        assert result.is_valid
        assert result.segment.is_split is True
        assert result.segment.pnum == 3
        assert result.segment.pno == 1

    def test_parse_heartbeat(self):
        """Test parsing heartbeat packet"""
        data_segment = (
            "QN=20240101120000000;"
            "ST=31;"
            "CN=9013;"  # Heartbeat command
            "MN=222222222222222222222222;"
            "Flag=4"    # No CP content for heartbeat
        )

        packet = self.create_test_packet(data_segment)
        result = self.parser.parse(packet)

        assert result.is_valid
        assert result.segment.cn == "9013"
        assert result.command_type == "HEARTBEAT"
        assert len(result.parameters) == 0

    def test_parse_with_multiple_parameters(self):
        """Test parsing packet with multiple parameter attributes"""
        data_segment = (
            "QN=20240101120000000;"
            "ST=32;"  # Surface water
            "CN=2061;"  # Hour data
            "MN=333333333333333333333333;"
            "Flag=5;"
            "CP=&&DataTime=20240101120000;"
            "w01001-Rtd=7.5,w01001-Min=7.2,w01001-Max=7.8,w01001-Avg=7.5,w01001-Flag=N;"
            "w01018-Rtd=30.0,w01018-Min=28.5,w01018-Max=31.2,w01018-Avg=29.8,w01018-Flag=N&&"
        )

        packet = self.create_test_packet(data_segment)
        result = self.parser.parse(packet)

        assert result.is_valid
        assert result.segment.st == "32"

        # Check w01001 parameters
        param1 = result.parameters["w01001"]
        assert param1.rtd == 7.5
        assert param1.min == 7.2
        assert param1.max == 7.8
        assert param1.avg == 7.5
        assert param1.flag == "N"

        # Check w01018 parameters
        param2 = result.parameters["w01018"]
        assert param2.rtd == 30.0
        assert param2.min == 28.5
        assert param2.max == 31.2
        assert param2.avg == 29.8

    def test_parse_invalid_crc(self):
        """Test parsing packet with invalid CRC"""
        data_segment = "QN=20240101120000000;ST=31;CN=2011;MN=444444444444444444444444;Flag=5;CP=&&&&"

        # Create packet with invalid CRC
        packet = self.create_test_packet(data_segment, calculate_crc=False)

        # Parse with CRC validation enabled
        parser_strict = HJ212Parser(ParserConfig(validate_crc=True, strict_mode=False))
        result = parser_strict.parse(packet)

        assert not result.is_valid
        assert "CRC validation failed" in result.errors[0]

    def test_parse_malformed_packet(self):
        """Test parsing malformed packet"""
        # Missing header
        packet1 = b"0100QN=20240101120000000;ST=31;CN=2011;MN=555555555555555555555555;Flag=50000\r\n"
        result1 = self.parser.parse(packet1)
        assert not result1.is_valid

        # Missing tail
        packet2 = b"##0100QN=20240101120000000;ST=31;CN=2011;MN=555555555555555555555555;Flag=50000"
        result2 = self.parser.parse(packet2)
        assert not result2.is_valid

        # Wrong data length
        packet3 = b"##9999QN=20240101120000000;ST=31;CN=2011;MN=555555555555555555555555;Flag=50000\r\n"
        result3 = self.parser.parse(packet3)
        assert not result3.is_valid

    def test_parse_air_quality_data(self):
        """Test parsing air quality monitoring data"""
        data_segment = (
            "QN=20240101120000000;"
            "ST=22;"  # Air quality
            "CN=2011;"
            "MN=666666666666666666666666;"
            "Flag=5;"
            "CP=&&DataTime=20240101120000;"
            "a01011-Rtd=15.3,a01011-Flag=N;"    # Smoke flow rate
            "a01012-Rtd=120.5,a01012-Flag=N;"   # Smoke temperature
            "a34013-Rtd=25.6,a34013-Flag=N;"    # Particulate matter
            "a21026-Rtd=85.3,a21026-Flag=N;"    # SO2
            "a21002-Rtd=120.8,a21002-Flag=N&&"  # NOx
        )

        packet = self.create_test_packet(data_segment)
        result = self.parser.parse(packet)

        assert result.is_valid
        assert result.segment.st == "22"
        assert result.system_type == "AIR_QUALITY"

        # Verify air quality parameters
        assert result.parameters["a01011"].rtd == 15.3   # Flow rate
        assert result.parameters["a01012"].rtd == 120.5  # Temperature
        assert result.parameters["a34013"].rtd == 25.6   # PM
        assert result.parameters["a21026"].rtd == 85.3   # SO2
        assert result.parameters["a21002"].rtd == 120.8  # NOx

    def test_format_response(self):
        """Test formatting ACK response for received packet"""
        data_segment = (
            "QN=20240101120000000;"
            "ST=31;"
            "CN=2011;"
            "PW=123456;"
            "MN=777777777777777777777777;"
            "Flag=5;"
            "CP=&&w01001-Rtd=7.5&&"
        )

        packet = self.create_test_packet(data_segment)
        result = self.parser.parse(packet)

        # Format response
        response = self.parser.format_response(result)

        # Parse the response to verify it's valid
        response_parsed = self.parser.parse(response)
        assert response_parsed.is_valid
        assert response_parsed.segment.cn == "9014"  # Data ACK
        assert response_parsed.segment.mn == "777777777777777777777777"
        assert "Result=1" in response_parsed.segment.cp

    def test_version_detection_edge_cases(self):
        """Test version detection with various flag values"""
        test_cases = [
            (0, ProtocolVersion.HJ212_2017),     # Version 0 -> default to 2017
            (4, ProtocolVersion.HJ212_2017),     # Version 1 (4 >> 2 = 1)
            (5, ProtocolVersion.HJ212_2017),     # Version 1 with ACK
            (8, ProtocolVersion.HJ212_2025),     # Version 2 (8 >> 2 = 2)
            (12, ProtocolVersion.HJ212_2025),    # Version 3 (12 >> 2 = 3)
            (252, ProtocolVersion.HJ212_2025),   # Max version (252 >> 2 = 63)
        ]

        for flag_value, expected_version in test_cases:
            data_segment = f"QN=20240101120000000;ST=31;CN=2011;MN=888888888888888888888888;Flag={flag_value};CP=&&&&"
            packet = self.create_test_packet(data_segment)
            result = self.parser.parse(packet)
            assert result.version == expected_version, f"Flag {flag_value} should detect as {expected_version}"

    def test_encrypted_content_detection(self):
        """Test detection of encrypted CP content (2025 feature)"""
        # Simulate encrypted content (hex string)
        encrypted_hex = "4A6F686E20446F65"  # Example hex data
        data_segment = (
            "QN=20250101120000000;"
            "ST=31;"
            "CN=2011;"
            "MN=999999999999999999999999;"
            "Flag=9;"  # Version 2 (2025)
            f"CP=&&{encrypted_hex}&&"
        )

        packet = self.create_test_packet(data_segment)

        # Parse without decryption key
        parser_no_key = HJ212Parser(ParserConfig(auto_decrypt=True, sm4_key=None))
        result = parser_no_key.parse(packet)

        assert result.version == ProtocolVersion.HJ212_2025
        assert result.is_encrypted is True
        assert "encrypted but no decryption key" in str(result.errors)


def test_crc_calculation():
    """Test CRC16 calculation independently"""
    from app.protocols.crc import calculate_crc16, crc16_to_hex, verify_crc

    test_data = b"Test123"
    crc = calculate_crc16(test_data)
    crc_hex = crc16_to_hex(crc)

    # Verify format
    assert len(crc_hex) == 4
    assert all(c in "0123456789ABCDEF" for c in crc_hex)

    # Verify validation
    assert verify_crc(test_data, crc_hex) is True
    assert verify_crc(test_data, "0000") is False


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])