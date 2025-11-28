"""Tests for HJ 212 protocol parser."""

import pytest
from datetime import datetime

from app.gateway.hj212_parser import HJ212Parser, HJ212Packet


class TestHJ212Parser:
    """Test cases for HJ 212 parser."""

    def setup_method(self) -> None:
        """Setup parser instance."""
        self.parser = HJ212Parser()

    def test_parse_realtime_data(self) -> None:
        """Test parsing realtime monitoring data packet."""
        # Sample HJ 212 packet for realtime data (CN=2011)
        packet_data = (
            "##0234;QN=20231101120000000;ST=32;CN=2011;PW=123456;"
            "MN=88888880000001;Flag=4;CP=&&DataTime=20231101120000;"
            "w01018-Rtd=6.5,w01018-Flag=N;w01001-Rtd=25.3,w01001-Flag=N&&;CRC1\r\n"
        )

        packet = self.parser.parse(packet_data)

        assert packet is not None
        assert packet.mn == "88888880000001"
        assert packet.cn == "2011"
        assert packet.st == "32"
        assert packet.is_realtime is True
        assert "pollutants" in packet.cp
        assert "w01018" in packet.cp["pollutants"]
        assert packet.cp["pollutants"]["w01018"]["Rtd"] == 6.5

    def test_parse_minute_data(self) -> None:
        """Test parsing minute average data packet."""
        packet_data = (
            "##0200;QN=20231101120000000;ST=32;CN=2051;PW=123456;"
            "MN=88888880000001;Flag=4;CP=&&DataTime=20231101120000;"
            "w01018-Avg=6.8,w01018-Min=6.2,w01018-Max=7.1&&;1234\r\n"
        )

        packet = self.parser.parse(packet_data)

        assert packet is not None
        assert packet.cn == "2051"
        assert packet.is_minute_data is True
        assert packet.cp["pollutants"]["w01018"]["Avg"] == 6.8

    def test_parse_heartbeat(self) -> None:
        """Test parsing heartbeat packet."""
        packet_data = (
            "##0100;QN=20231101120000000;ST=91;CN=9014;PW=123456;"
            "MN=88888880000001;Flag=0;CP=&&&&;ABCD\r\n"
        )

        packet = self.parser.parse(packet_data)

        assert packet is not None
        assert packet.cn == "9014"
        assert packet.is_heartbeat is True

    def test_parse_invalid_packet(self) -> None:
        """Test parsing invalid packet returns None."""
        invalid_data = "This is not a valid HJ 212 packet"
        packet = self.parser.parse(invalid_data)
        assert packet is None

    def test_parse_bytes_input(self) -> None:
        """Test parsing bytes input."""
        packet_data = (
            b"##0100;QN=20231101120000000;ST=91;CN=9014;PW=123456;"
            b"MN=88888880000001;Flag=0;CP=&&&&;ABCD\r\n"
        )

        packet = self.parser.parse(packet_data)
        assert packet is not None
        assert packet.mn == "88888880000001"

    def test_build_response(self) -> None:
        """Test building response packet."""
        packet = HJ212Packet(
            mn="88888880000001",
            st="32",
            pw="123456",
        )

        response = self.parser.build_response(packet, result_code=1)

        assert response is not None
        assert b"##" in response
        assert b"QnRtn=1" in response
        assert b"\r\n" in response

    def test_crc_calculation(self) -> None:
        """Test CRC calculation."""
        data = "test data for crc"
        crc = self.parser._calculate_crc(data.encode("utf-8"))

        assert len(crc) == 4
        assert all(c in "0123456789ABCDEF" for c in crc)

    def test_extract_pollutant_with_all_fields(self) -> None:
        """Test extracting pollutant data with all field types."""
        cp_data = (
            "DataTime=20231101120000;"
            "w01018-Rtd=6.5,w01018-Flag=N,w01018-Avg=6.3,"
            "w01018-Min=6.0,w01018-Max=7.0,w01018-Cou=100"
        )

        result = self.parser._parse_cp(cp_data)

        assert "pollutants" in result
        assert "w01018" in result["pollutants"]
        pollutant = result["pollutants"]["w01018"]
        assert pollutant["Rtd"] == 6.5
        assert pollutant["Flag"] == "N"
        assert pollutant["Avg"] == 6.3
        assert pollutant["Min"] == 6.0
        assert pollutant["Max"] == 7.0
        assert pollutant["Cou"] == 100.0
