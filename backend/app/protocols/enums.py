"""
HJ212 Protocol Enums and Constants

This module defines all the command codes, system codes, and parameter codes
used in HJ 212-2017 and HJ 212-2025 protocols.
"""

from enum import Enum, IntEnum


class SystemCode(str, Enum):
    """System codes for different monitoring types"""

    # Common for 2017/2025
    POLLUTION_SOURCE = "31"  # 环境污染源
    SURFACE_WATER = "32"     # 地表水
    AIR_QUALITY = "22"       # 空气质量

    # New in 2025
    WASTE_GAS_MONITORING = "42"  # 废气工况监控
    FACILITY_POWER = "44"        # 设施用电监控


class CommandCode(str, Enum):
    """Command codes for different data transmission types"""

    # Data upload commands
    REALTIME_DATA = "2011"      # 实时数据上报
    MINUTE_DATA = "2051"        # 分钟数据上报
    HOUR_DATA = "2061"          # 小时数据上报
    DAY_DATA = "2031"           # 日数据上报

    # System commands
    HEARTBEAT = "9013"          # 心跳包/通知应答
    DATA_ACK = "9014"           # 数据应答

    # Control commands
    SET_TIMEOUT = "1000"        # 设置超时时间及重发次数
    GET_TIME = "1011"           # 提取现场机时间
    SET_TIME = "1012"           # 设置现场机时间
    GET_REALTIME_DATA = "2011"  # 取实时数据

    # Status commands
    STATUS_REPORT = "2021"      # 状态上报
    LOG_REPORT = "2041"         # 日志上报


class ParameterCode(str, Enum):
    """Parameter codes for different monitoring items"""

    # Water quality parameters (w series) - 2017/2025 common
    W01001 = "w01001"  # pH值
    W01018 = "w01018"  # 化学需氧量 (COD)
    W21003 = "w21003"  # 氨氮
    W21011 = "w21011"  # 总磷
    W21001 = "w21001"  # 总氮
    W01009 = "w01009"  # 溶解氧
    W01010 = "w01010"  # 水温
    W01014 = "w01014"  # 电导率
    W01003 = "w01003"  # 浊度
    W19011 = "w19011"  # 总余氯

    # Air quality parameters (a series) - 2017/2025 common
    A01011 = "a01011"  # 烟气流速
    A01012 = "a01012"  # 烟气温度
    A01013 = "a01013"  # 烟气压力
    A01014 = "a01014"  # 烟气湿度
    A34013 = "a34013"  # 烟尘(颗粒物)
    A21026 = "a21026"  # 二氧化硫 (SO2)
    A21002 = "a21002"  # 氮氧化物 (NOx)
    A21003 = "a21003"  # 一氧化碳 (CO)
    A05001 = "a05001"  # PM2.5
    A05002 = "a05002"  # PM10

    # Power parameters (d series) - 2025 specific
    D10001 = "d10001"  # 总有功功率
    D10002 = "d10002"  # 总无功功率
    D10003 = "d10003"  # 总视在功率
    D10004 = "d10004"  # A相电压
    D10005 = "d10005"  # B相电压
    D10006 = "d10006"  # C相电压
    D10007 = "d10007"  # A相电流
    D10008 = "d10008"  # B相电流
    D10009 = "d10009"  # C相电流
    D10010 = "d10010"  # 功率因数

    # Production/treatment parameters (p series) - 2025 specific
    P10001 = "p10001"  # 风机电流
    P10002 = "p10002"  # 风机频率
    P10003 = "p10003"  # 风机转速
    P10004 = "p10004"  # 除尘器差压
    P10005 = "p10005"  # 脱硫塔液位

    # Auxiliary equipment status (i series) - 2025 specific
    I12001 = "i12001"  # 运行状态
    I12002 = "i12002"  # 故障状态
    I12003 = "i12003"  # 维护状态
    I12004 = "i12004"  # 在线率
    I12005 = "i12005"  # 数据有效率


class DataFlag(str, Enum):
    """Data flags for parameter values"""

    NORMAL = "N"           # 正常
    ALARM = "A"            # 报警
    MAINTENANCE = "M"      # 维护
    FAULT = "F"            # 故障
    CALIBRATION = "C"      # 校准
    INVALID = "D"          # 无效数据
    SYSTEM_ERROR = "S"     # 系统错误
    TIMEOUT = "T"          # 超时
    OVERRANGE = "O"        # 超量程


class ProtocolVersion(IntEnum):
    """Protocol versions"""

    HJ212_2017 = 1  # Version 1: HJ 212-2017
    HJ212_2025 = 2  # Version 2: HJ 212-2025


class FlagBits(IntEnum):
    """Flag bits definition"""

    # Bit positions
    ACK_BIT = 0           # Bit 0: 0=no ack, 1=need ack
    SPLIT_BIT = 1         # Bit 1: 0=no split, 1=has split
    VERSION_START = 2     # Bit 2-7: Version number (6 bits)
    VERSION_MASK = 0xFC   # Mask for version bits (11111100)


# Parameter descriptions mapping
PARAMETER_DESCRIPTIONS = {
    # Water quality
    "w01001": "pH值",
    "w01018": "化学需氧量(COD)",
    "w21003": "氨氮",
    "w21011": "总磷",
    "w21001": "总氮",
    "w01009": "溶解氧",
    "w01010": "水温",
    "w01014": "电导率",
    "w01003": "浊度",
    "w19011": "总余氯",

    # Air quality
    "a01011": "烟气流速",
    "a01012": "烟气温度",
    "a01013": "烟气压力",
    "a01014": "烟气湿度",
    "a34013": "烟尘(颗粒物)",
    "a21026": "二氧化硫(SO2)",
    "a21002": "氮氧化物(NOx)",
    "a21003": "一氧化碳(CO)",
    "a05001": "PM2.5",
    "a05002": "PM10",

    # Power parameters (2025)
    "d10001": "总有功功率",
    "d10002": "总无功功率",
    "d10003": "总视在功率",
    "d10004": "A相电压",
    "d10005": "B相电压",
    "d10006": "C相电压",
    "d10007": "A相电流",
    "d10008": "B相电流",
    "d10009": "C相电流",
    "d10010": "功率因数",

    # Production/treatment (2025)
    "p10001": "风机电流",
    "p10002": "风机频率",
    "p10003": "风机转速",
    "p10004": "除尘器差压",
    "p10005": "脱硫塔液位",

    # Auxiliary equipment (2025)
    "i12001": "运行状态",
    "i12002": "故障状态",
    "i12003": "维护状态",
    "i12004": "在线率",
    "i12005": "数据有效率",
}


# Parameter units mapping
PARAMETER_UNITS = {
    # Water quality
    "w01001": "",         # pH无单位
    "w01018": "mg/L",
    "w21003": "mg/L",
    "w21011": "mg/L",
    "w21001": "mg/L",
    "w01009": "mg/L",
    "w01010": "℃",
    "w01014": "μS/cm",
    "w01003": "NTU",
    "w19011": "mg/L",

    # Air quality
    "a01011": "m/s",
    "a01012": "℃",
    "a01013": "kPa",
    "a01014": "%",
    "a34013": "mg/m³",
    "a21026": "mg/m³",
    "a21002": "mg/m³",
    "a21003": "mg/m³",
    "a05001": "μg/m³",
    "a05002": "μg/m³",

    # Power parameters
    "d10001": "kW",
    "d10002": "kVar",
    "d10003": "kVA",
    "d10004": "V",
    "d10005": "V",
    "d10006": "V",
    "d10007": "A",
    "d10008": "A",
    "d10009": "A",
    "d10010": "",        # 功率因数无单位

    # Production/treatment
    "p10001": "A",
    "p10002": "Hz",
    "p10003": "rpm",
    "p10004": "Pa",
    "p10005": "m",

    # Auxiliary equipment
    "i12001": "",        # 状态值无单位
    "i12002": "",
    "i12003": "",
    "i12004": "%",
    "i12005": "%",
}