"""
HJ 212-2017/2025 标准水质监测污染物定义库

根据《污染物在线监控（监测）系统数据传输标准》(HJ 212-2017/2025)定义
包含完整的水质监测指标，支持全量水质监测平台。

使用说明:
- POLLUTANT_MAP: 标准污染物字典，key为HJ 212编码
- get_pollutant_info(): 获取污染物信息
- get_all_pollutant_codes(): 获取所有污染物编码列表
- format_value(): 根据精度格式化数值
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, TypedDict


class PollutantInfo(TypedDict):
    """污染物信息类型定义"""
    name: str       # 中文名称
    unit: str       # 计量单位
    precision: int  # 小数位数


# ============================================================================
# HJ 212-2017/2025 水质监测污染物标准字典
# ============================================================================
POLLUTANT_MAP: dict[str, PollutantInfo] = {
    # =========================================================================
    # 常规五参数 & 物理指标
    # =========================================================================
    "w00000": {"name": "瞬时流量", "unit": "L/s", "precision": 2},
    "w00001": {"name": "累计流量", "unit": "m³", "precision": 2},
    "w01001": {"name": "pH值", "unit": "无量纲", "precision": 2},
    "w01010": {"name": "水温", "unit": "℃", "precision": 1},
    "w01003": {"name": "浊度", "unit": "NTU", "precision": 1},
    "w01014": {"name": "电导率", "unit": "μS/cm", "precision": 1},
    "w01009": {"name": "溶解氧", "unit": "mg/L", "precision": 2},
    "w01008": {"name": "色度", "unit": "度", "precision": 0},
    "w01002": {"name": "透明度", "unit": "cm", "precision": 0},
    "w01012": {"name": "氧化还原电位", "unit": "mV", "precision": 1},
    "w01004": {"name": "悬浮物", "unit": "mg/L", "precision": 1},

    # =========================================================================
    # 有机物 & 耗氧量指标
    # =========================================================================
    "w01018": {"name": "化学需氧量(CODcr)", "unit": "mg/L", "precision": 2},
    "w01019": {"name": "高锰酸盐指数(CODMn)", "unit": "mg/L", "precision": 2},
    "w01017": {"name": "生化需氧量(BOD5)", "unit": "mg/L", "precision": 2},
    "w01020": {"name": "总有机碳(TOC)", "unit": "mg/L", "precision": 2},
    "w23002": {"name": "挥发酚", "unit": "mg/L", "precision": 4},
    "w22001": {"name": "石油类", "unit": "mg/L", "precision": 3},
    "w23001": {"name": "动植物油", "unit": "mg/L", "precision": 2},
    "w19001": {"name": "阴离子表面活性剂", "unit": "mg/L", "precision": 3},

    # =========================================================================
    # 营养盐 (氮磷系列)
    # =========================================================================
    "w21003": {"name": "氨氮", "unit": "mg/L", "precision": 3},
    "w21001": {"name": "总氮", "unit": "mg/L", "precision": 2},
    "w21011": {"name": "总磷", "unit": "mg/L", "precision": 3},
    "w21006": {"name": "亚硝酸盐氮", "unit": "mg/L", "precision": 3},
    "w21007": {"name": "硝酸盐氮", "unit": "mg/L", "precision": 2},
    "w21023": {"name": "磷酸盐", "unit": "mg/L", "precision": 3},
    "w21002": {"name": "凯氏氮", "unit": "mg/L", "precision": 2},
    "w21004": {"name": "游离氨", "unit": "mg/L", "precision": 3},
    "w21019": {"name": "正磷酸盐", "unit": "mg/L", "precision": 3},

    # =========================================================================
    # 毒性阴离子
    # =========================================================================
    "w21017": {"name": "氟化物", "unit": "mg/L", "precision": 3},
    "w21016": {"name": "氰化物", "unit": "mg/L", "precision": 4},
    "w21022": {"name": "硫化物", "unit": "mg/L", "precision": 3},
    "w21038": {"name": "硫酸盐", "unit": "mg/L", "precision": 1},
    "w21039": {"name": "氯化物", "unit": "mg/L", "precision": 1},

    # =========================================================================
    # 重金属 - 核心差异化指标 (高精度要求)
    # =========================================================================
    # 一类重金属 (毒性最强，限值最低)
    "w20111": {"name": "总汞", "unit": "mg/L", "precision": 5},       # 限值0.001 mg/L
    "w20115": {"name": "总镉", "unit": "mg/L", "precision": 5},       # 限值0.01 mg/L
    "w20117": {"name": "六价铬", "unit": "mg/L", "precision": 4},     # 限值0.05 mg/L
    "w20119": {"name": "总砷", "unit": "mg/L", "precision": 4},       # 限值0.1 mg/L
    "w20120": {"name": "总铅", "unit": "mg/L", "precision": 4},       # 限值0.1 mg/L

    # 二类重金属
    "w20116": {"name": "总铬", "unit": "mg/L", "precision": 4},
    "w20122": {"name": "总铜", "unit": "mg/L", "precision": 3},
    "w20123": {"name": "总锌", "unit": "mg/L", "precision": 3},
    "w20121": {"name": "总镍", "unit": "mg/L", "precision": 3},
    "w20124": {"name": "总锰", "unit": "mg/L", "precision": 3},
    "w20125": {"name": "总铁", "unit": "mg/L", "precision": 2},
    "w20126": {"name": "总银", "unit": "mg/L", "precision": 4},
    "w20127": {"name": "总铝", "unit": "mg/L", "precision": 3},
    "w20128": {"name": "总钡", "unit": "mg/L", "precision": 3},
    "w20129": {"name": "总铍", "unit": "mg/L", "precision": 5},
    "w20130": {"name": "总铋", "unit": "mg/L", "precision": 4},
    "w20038": {"name": "总钴", "unit": "mg/L", "precision": 4},
    "w20141": {"name": "总锑", "unit": "mg/L", "precision": 4},
    "w20092": {"name": "总锡", "unit": "mg/L", "precision": 3},
    "w20131": {"name": "总硒", "unit": "mg/L", "precision": 4},
    "w20023": {"name": "总铊", "unit": "mg/L", "precision": 5},
    "w20101": {"name": "总钒", "unit": "mg/L", "precision": 4},
    "w20113": {"name": "总钼", "unit": "mg/L", "precision": 4},

    # =========================================================================
    # 有机污染物
    # =========================================================================
    "w23003": {"name": "苯", "unit": "mg/L", "precision": 4},
    "w23004": {"name": "甲苯", "unit": "mg/L", "precision": 4},
    "w23005": {"name": "乙苯", "unit": "mg/L", "precision": 4},
    "w23006": {"name": "二甲苯", "unit": "mg/L", "precision": 4},
    "w23007": {"name": "苯乙烯", "unit": "mg/L", "precision": 4},
    "w24001": {"name": "苯并芘", "unit": "μg/L", "precision": 4},
    "w25001": {"name": "三氯甲烷", "unit": "mg/L", "precision": 4},
    "w25002": {"name": "四氯化碳", "unit": "mg/L", "precision": 4},
    "w25038": {"name": "三氯乙烯", "unit": "mg/L", "precision": 4},
    "w25039": {"name": "四氯乙烯", "unit": "mg/L", "precision": 4},

    # =========================================================================
    # 农药类
    # =========================================================================
    "w33001": {"name": "六六六", "unit": "mg/L", "precision": 6},
    "w33007": {"name": "滴滴涕", "unit": "mg/L", "precision": 6},

    # =========================================================================
    # 微生物指标
    # =========================================================================
    "w02003": {"name": "粪大肠菌群", "unit": "个/L", "precision": 0},
    "w02001": {"name": "总大肠菌群", "unit": "个/L", "precision": 0},
    "w02008": {"name": "细菌总数", "unit": "CFU/mL", "precision": 0},

    # =========================================================================
    # 放射性指标
    # =========================================================================
    "w09001": {"name": "总α放射性", "unit": "Bq/L", "precision": 3},
    "w09002": {"name": "总β放射性", "unit": "Bq/L", "precision": 3},

    # =========================================================================
    # 其他综合指标
    # =========================================================================
    "w01016": {"name": "总硬度", "unit": "mg/L", "precision": 1},
    "w01006": {"name": "矿化度", "unit": "mg/L", "precision": 0},
    "w99001": {"name": "叶绿素a", "unit": "mg/m³", "precision": 2},
    "w99002": {"name": "藻密度", "unit": "万个/L", "precision": 0},
}


# 默认厂商私有/历史编码别名映射到标准 HJ212 编码
DEFAULT_POLLUTANT_CODE_ALIASES: dict[str, str] = {
    "b01": "w00000",  # 部分数采仪将瞬时流量上报为 B01
}


def _parse_aliases_from_string(raw_aliases: str) -> dict[str, str]:
    """Parse alias mapping from JSON or simple `a=b,c=d` format."""
    value = (raw_aliases or "").strip()
    if not value:
        return {}

    # Preferred format: JSON object, e.g. {"b01": "w00000"}
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            result: dict[str, str] = {}
            for alias_code, target_code in parsed.items():
                alias = str(alias_code).strip().lower()
                target = str(target_code).strip().lower()
                if alias and target:
                    result[alias] = target
            return result
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    # Fallback format: b01=w00000,b02=w00001
    result: dict[str, str] = {}
    for pair in value.split(","):
        alias_code, separator, target_code = pair.partition("=")
        if separator != "=":
            continue
        alias = alias_code.strip().lower()
        target = target_code.strip().lower()
        if alias and target:
            result[alias] = target
    return result


@lru_cache(maxsize=1)
def get_pollutant_code_aliases() -> dict[str, str]:
    """Get effective alias mapping from defaults + environment overrides.

    Environment variable:
    - POLLUTANT_CODE_ALIASES
      - JSON object: {"b01":"w00000","f01":"w00000"}
      - or simple pairs: b01=w00000,f01=w00000
    """
    aliases = dict(DEFAULT_POLLUTANT_CODE_ALIASES)
    configured_aliases = _parse_aliases_from_string(os.getenv("POLLUTANT_CODE_ALIASES", ""))
    aliases.update(configured_aliases)
    return aliases


# ============================================================================
# 辅助函数
# ============================================================================

def normalize_pollutant_code(code: str) -> str:
    """Normalize pollutant code to canonical HJ212 code when possible."""
    normalized = (code or "").strip().lower()
    return get_pollutant_code_aliases().get(normalized, normalized)


def get_pollutant_code_candidates(code: str) -> list[str]:
    """Get all equivalent code candidates for DB query filtering."""
    raw_code = (code or "").strip()
    if not raw_code:
        return []

    lower_code = raw_code.lower()
    canonical_code = normalize_pollutant_code(lower_code)

    candidates: list[str] = []

    def _add(candidate: str) -> None:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    _add(raw_code)
    _add(lower_code)
    _add(canonical_code)

    for alias_code, target_code in get_pollutant_code_aliases().items():
        if target_code == canonical_code:
            _add(alias_code)
            _add(alias_code.upper())

    return candidates

def get_pollutant_info(code: str) -> PollutantInfo | None:
    """
    获取污染物信息

    Args:
        code: HJ 212 污染物编码 (如 'w01018')

    Returns:
        污染物信息字典，不存在返回 None
    """
    normalized_code = normalize_pollutant_code(code)
    return POLLUTANT_MAP.get(normalized_code)


def get_pollutant_name(code: str) -> str:
    """
    获取污染物名称

    Args:
        code: HJ 212 污染物编码

    Returns:
        污染物名称，不存在返回编码本身
    """
    info = get_pollutant_info(code)
    return info["name"] if info else code


def get_all_pollutant_codes() -> list[str]:
    """获取所有已定义的污染物编码列表"""
    return list(POLLUTANT_MAP.keys())


def is_known_pollutant(code: str) -> bool:
    """判断是否为已知污染物编码"""
    return normalize_pollutant_code(code) in POLLUTANT_MAP


def format_value(code: str, value: float) -> str:
    """
    根据污染物精度要求格式化数值

    Args:
        code: 污染物编码
        value: 原始数值

    Returns:
        格式化后的字符串
    """
    info = get_pollutant_info(code)
    precision = info["precision"] if info else 2
    return f"{value:.{precision}f}"


def get_pollutant_column_name(code: str) -> str:
    """
    生成数据库列名 (将编码转为有效的SQL标识符)

    Args:
        code: 污染物编码 (如 'w01018')

    Returns:
        列名 (如 'w01018')
    """
    # HJ 212 编码已经是有效的SQL标识符格式
    return normalize_pollutant_code(code)


def get_tdengine_columns_definition() -> str:
    """
    生成 TDengine 超级表的所有污染物列定义

    Returns:
        SQL 列定义字符串，如 "w01001 DOUBLE, w01010 DOUBLE, ..."
    """
    columns = []
    for code in POLLUTANT_MAP.keys():
        # 每个污染物有 value 和 flag 两个字段
        columns.append(f"{code}_val DOUBLE")
        columns.append(f"{code}_flag NCHAR(8)")
    return ",\n                    ".join(columns)


# ============================================================================
# 污染物分类索引 (便于按类别查询)
# ============================================================================

POLLUTANT_CATEGORIES: dict[str, list[str]] = {
    "physical": [
        "w00000", "w00001", "w01001", "w01010", "w01003",
        "w01014", "w01009", "w01008", "w01002", "w01012", "w01004"
    ],
    "organic": [
        "w01018", "w01019", "w01017", "w01020", "w23002",
        "w22001", "w23001", "w19001"
    ],
    "nitrogen_phosphorus": [
        "w21003", "w21001", "w21011", "w21006", "w21007",
        "w21023", "w21002", "w21004", "w21019"
    ],
    "toxic_anions": [
        "w21017", "w21016", "w21022", "w21038", "w21039"
    ],
    "heavy_metals_class1": [
        "w20111", "w20115", "w20117", "w20119", "w20120"
    ],
    "heavy_metals_class2": [
        "w20116", "w20122", "w20123", "w20121", "w20124", "w20125",
        "w20126", "w20127", "w20128", "w20129", "w20130", "w20038",
        "w20141", "w20092", "w20131", "w20023", "w20101", "w20113"
    ],
    "organic_pollutants": [
        "w23003", "w23004", "w23005", "w23006", "w23007",
        "w24001", "w25001", "w25002", "w25038", "w25039"
    ],
    "pesticides": ["w33001", "w33007"],
    "microorganism": ["w02003", "w02001", "w02008"],
    "radioactive": ["w09001", "w09002"],
    "comprehensive": ["w01016", "w01006", "w99001", "w99002"],
}


def get_pollutants_by_category(category: str) -> list[dict[str, Any]]:
    """
    按分类获取污染物列表

    Args:
        category: 分类名称 (如 'heavy_metals_class1')

    Returns:
        污染物信息列表
    """
    codes = POLLUTANT_CATEGORIES.get(category, [])
    return [
        {"code": code, **POLLUTANT_MAP[code]}
        for code in codes
        if code in POLLUTANT_MAP
    ]


def get_all_categories() -> list[str]:
    """获取所有污染物分类名称"""
    return list(POLLUTANT_CATEGORIES.keys())
