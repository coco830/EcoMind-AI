"""HJ 212-2017/2025 Protocol Parser.

HJ 212 is China's environmental monitoring data transmission standard.
Packet format: ##DataLen=nnnn;Data;CRC\\r\\n
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class HJ212Packet:
    """Parsed HJ 212 protocol packet."""

    qn: str = ""  # 请求编码 QN=YYYYMMDDHHmmssZZZ
    st: str = ""  # 系统编码 ST=nn
    cn: str = ""  # 命令编码 CN=nnnn
    pw: str = ""  # 访问密码 PW=xxxxxx
    mn: str = ""  # 设备唯一标识 MN=xxxxxxxxxxxxxxx
    flag: int = 0  # 标志位 Flag=n
    cp: dict[str, Any] = field(default_factory=dict)  # 指令参数 CP=&&...&&
    raw_data: str = ""  # 原始数据段
    crc: str = ""  # CRC校验码

    @property
    def is_realtime(self) -> bool:
        """Check if this is real-time data (CN=2011)."""
        return self.cn == "2011"

    @property
    def is_minute_data(self) -> bool:
        """Check if this is minute average data (CN=2051)."""
        return self.cn == "2051"

    @property
    def is_hour_data(self) -> bool:
        """Check if this is hour average data (CN=2061)."""
        return self.cn == "2061"

    @property
    def is_heartbeat(self) -> bool:
        """Check if this is heartbeat packet."""
        return self.cn == "9014"


class HJ212Parser:
    """Parser for HJ 212 protocol packets."""

    # Packet pattern: ##DataLen=nnnn;Data;CRC\r\n
    PACKET_PATTERN = re.compile(
        r"##(\d{4});([^;]+);([A-Fa-f0-9]{4})\r?\n?"
    )

    # Field patterns
    FIELD_PATTERNS = {
        "QN": re.compile(r"QN=(\d{17})"),
        "ST": re.compile(r"ST=(\d{2})"),
        "CN": re.compile(r"CN=(\d{4})"),
        "PW": re.compile(r"PW=(\w+)"),
        "MN": re.compile(r"MN=(\w+)"),
        "Flag": re.compile(r"Flag=(\d+)"),
        "CP": re.compile(r"CP=&&(.+?)&&", re.DOTALL),
    }

    # CP field patterns for pollutant data
    # Format: polcode-Rtd=value,polcode-Flag=flag;
    POLLUTANT_PATTERN = re.compile(
        r"([a-zA-Z0-9]+)-(Rtd|Flag|Avg|Min|Max|Cou|SampleTime)=([^,;]+)"
    )

    def __init__(self) -> None:
        """Initialize parser."""
        pass

    def parse(self, data: bytes | str) -> HJ212Packet | None:
        """Parse HJ 212 packet from raw data."""
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                # Try GB2312 encoding
                try:
                    data = data.decode("gb2312")
                except UnicodeDecodeError:
                    return None

        match = self.PACKET_PATTERN.search(data)
        if not match:
            return None

        data_len = int(match.group(1))
        raw_data = match.group(2)
        crc = match.group(3)

        # Verify data length
        if len(raw_data) != data_len:
            pass  # Log warning but continue parsing

        # Verify CRC
        if not self._verify_crc(raw_data, crc):
            pass  # Log warning but continue parsing

        packet = HJ212Packet(raw_data=raw_data, crc=crc)

        # Extract fields
        for field_name, pattern in self.FIELD_PATTERNS.items():
            field_match = pattern.search(raw_data)
            if field_match:
                value = field_match.group(1)
                if field_name == "Flag":
                    setattr(packet, field_name.lower(), int(value))
                elif field_name == "CP":
                    packet.cp = self._parse_cp(value)
                else:
                    setattr(packet, field_name.lower(), value)

        return packet

    def _parse_cp(self, cp_data: str) -> dict[str, Any]:
        """Parse CP (Command Parameter) section."""
        result: dict[str, Any] = {}

        # Parse DataTime if present
        datatime_match = re.search(r"DataTime=(\d{14})", cp_data)
        if datatime_match:
            result["DataTime"] = datetime.strptime(
                datatime_match.group(1), "%Y%m%d%H%M%S"
            )

        # Parse pollutant data
        pollutants: dict[str, dict[str, Any]] = {}
        for match in self.POLLUTANT_PATTERN.finditer(cp_data):
            pol_code = match.group(1)
            field_type = match.group(2)
            value = match.group(3)

            if pol_code not in pollutants:
                pollutants[pol_code] = {}

            # Convert numeric values
            if field_type in ("Rtd", "Avg", "Min", "Max", "Cou"):
                try:
                    pollutants[pol_code][field_type] = float(value)
                except ValueError:
                    pollutants[pol_code][field_type] = value
            else:
                pollutants[pol_code][field_type] = value

        if pollutants:
            result["pollutants"] = pollutants

        return result

    def _verify_crc(self, data: str, expected_crc: str) -> bool:
        """Verify CRC-16 checksum."""
        calculated = self._calculate_crc(data.encode("utf-8"))
        return calculated.upper() == expected_crc.upper()

    def _calculate_crc(self, data: bytes) -> str:
        """Calculate CRC-16 checksum."""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return f"{crc:04X}"

    def build_response(
        self,
        packet: HJ212Packet,
        result_code: int = 1,
        result_info: str = "",
    ) -> bytes:
        """Build response packet for acknowledgment."""
        qn = datetime.now().strftime("%Y%m%d%H%M%S") + "000"
        st = packet.st or "91"
        cn = "9014"  # Ack command
        pw = packet.pw or "123456"
        mn = packet.mn

        cp_content = f"QnRtn={result_code}"
        if result_info:
            cp_content += f",ExeRtn={result_info}"

        data = (
            f"QN={qn};ST={st};CN={cn};PW={pw};MN={mn};"
            f"Flag=0;CP=&&{cp_content}&&"
        )

        data_len = len(data)
        crc = self._calculate_crc(data.encode("utf-8"))

        response = f"##{data_len:04d};{data};{crc}\r\n"
        return response.encode("utf-8")
