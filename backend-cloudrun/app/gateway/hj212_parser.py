from __future__ import annotations

"""HJ 212-2017/2025 Protocol Parser.

HJ 212 is China's environmental monitoring data transmission standard.
标准数据包格式: ##DataLenDataCRC\r\n
例如: ##0130QN=20251207145051148;ST=32;CN=2011;PW=123456;MN=125301024WHYY1;Flag=4;CP=&&DataTime=20251207145000;...&&ABCD\r\n
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

    @property
    def is_login(self) -> bool:
        """Check if this is device login request (CN=9021)."""
        return self.cn == "9021"


class HJ212Parser:
    """Parser for HJ 212 protocol packets."""

    # Field patterns - 用于从数据内容中提取各字段
    FIELD_PATTERNS = {
        "QN": re.compile(r"QN=(\d{17})"),
        "ST": re.compile(r"ST=(\d{2})"),
        "CN": re.compile(r"CN=(\d{4})"),
        "PW": re.compile(r"PW=(\w+)"),
        "MN": re.compile(r"MN=([\w-]+)"),  # MN可能包含字母数字和连字符
        "Flag": re.compile(r"Flag=(\d+)"),
        "CP": re.compile(r"CP=&&(.*?)&&", re.DOTALL),  # 使用 * 允许空内容
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
        """Parse HJ 212 packet from raw data.

        HJ212 标准格式: ##DataLenDataCRC\r\n
        - ## 起始符
        - DataLen 4位数字，表示Data部分的字节长度
        - Data 数据内容
        - CRC 4位十六进制校验码
        - \r\n 结束符
        """
        if isinstance(data, bytes):
            try:
                data = data.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    data = data.decode("gb2312")
                except UnicodeDecodeError:
                    return None

        # 查找 ## 起始符
        start_idx = data.find("##")
        if start_idx == -1:
            return None

        # 从 ## 后提取4位数据长度
        len_start = start_idx + 2
        if len(data) < len_start + 4:
            return None

        try:
            data_len = int(data[len_start:len_start + 4])
        except ValueError:
            return None

        # 数据内容起始位置
        data_start = len_start + 4

        # 数据内容 (长度为 data_len)
        if len(data) < data_start + data_len:
            # 数据不完整，尝试宽松解析
            raw_data = data[data_start:]
        else:
            raw_data = data[data_start:data_start + data_len]

        # CRC 在数据内容之后 (4位十六进制)
        crc_start = data_start + data_len
        if len(data) >= crc_start + 4:
            crc = data[crc_start:crc_start + 4]
        else:
            crc = ""

        # 创建数据包对象
        packet = HJ212Packet(raw_data=raw_data, crc=crc)

        # 提取各字段
        for field_name, pattern in self.FIELD_PATTERNS.items():
            field_match = pattern.search(raw_data)
            if field_match:
                value = field_match.group(1)
                if field_name == "Flag":
                    try:
                        setattr(packet, field_name.lower(), int(value))
                    except ValueError:
                        setattr(packet, field_name.lower(), 0)
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
            try:
                result["DataTime"] = datetime.strptime(
                    datatime_match.group(1), "%Y%m%d%H%M%S"
                )
            except ValueError:
                pass

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
        error: bool = False,
    ) -> bytes:
        """Build response packet for acknowledgment."""
        qn = datetime.now().strftime("%Y%m%d%H%M%S") + "000"
        st = packet.st or "91"
        pw = packet.pw or "123456"
        mn = packet.mn

        # 根据请求类型决定响应命令
        if packet.is_login:
            cn = "9022"  # 登录响应
        else:
            cn = "9014"  # 通用确认

        cp_content = f"QnRtn={result_code}"
        if result_info:
            cp_content += f",ExeRtn={result_info}"

        data = (
            f"QN={qn};ST={st};CN={cn};PW={pw};MN={mn};"
            f"Flag=0;CP=&&{cp_content}&&"
        )

        data_len = len(data)
        crc = self._calculate_crc(data.encode("utf-8"))

        # HJ212 标准响应格式
        response = f"##{data_len:04d}{data}{crc}\r\n"
        return response.encode("utf-8")
