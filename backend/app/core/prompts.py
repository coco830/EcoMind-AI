"""
EcoMind AI Prompt 模板系统

支持全要素环保监测：废水、废气、噪音、土壤
动态注入领域知识，生成专业化的 AI 诊断提示词
"""

from enum import Enum
from typing import Any


class MonitorDomain(str, Enum):
    """监测领域枚举"""

    WATER = "water"
    AIR = "air"
    NOISE = "noise"
    SOIL = "soil"


# =============================================================================
# 领域知识库映射
# =============================================================================

DOMAIN_KNOWLEDGE: dict[str, dict[str, str]] = {
    "water": {
        "name": "废水",
        "standards": "《水污染源在线监测系统运行技术规范》(HJ 355)、《城镇污水处理厂污染物排放标准》(GB 18918-2002)、《污水综合排放标准》(GB 8978-1996)",
        "terms": "生化系统、曝气量、停留时间(HRT)、污泥负荷(F/M)、药剂投加比、去除率、溶解氧(DO)、污泥浓度(MLSS)、SVI值、回流比",
        "suggestions": "检查进水负荷变化、校准溶解氧(DO)探头、排查加药泵堵塞、检测曝气系统均匀性、核实污泥龄是否合理",
        "typical_pollutants": {
            "w01018": {"name": "COD", "unit": "mg/L", "limit": 50},
            "w01019": {"name": "BOD5", "unit": "mg/L", "limit": 10},
            "w21003": {"name": "氨氮", "unit": "mg/L", "limit": 5},
            "w21011": {"name": "总氮", "unit": "mg/L", "limit": 15},
            "w21001": {"name": "总磷", "unit": "mg/L", "limit": 0.5},
            "w01001": {"name": "pH", "unit": "", "limit_range": "6-9"},
            "w01010": {"name": "悬浮物", "unit": "mg/L", "limit": 10},
        },
    },
    "air": {
        "name": "废气",
        "standards": "《固定污染源烟气排放连续监测技术规范》(HJ 75)、《火电厂大气污染物排放标准》(GB 13223-2011)、《锅炉大气污染物排放标准》(GB 13271-2014)",
        "terms": "脱硫效率、脱硝喷氨量、布袋除尘压差、炉膛温度、氧含量折算、烟气流速、标态体积、湿度修正、CEMS系统",
        "suggestions": "检查CEMS伴热管线温度、核对标气校准记录、检查脱硫塔浆液pH值和密度、排查SCR催化剂积灰、检测布袋破损情况",
        "typical_pollutants": {
            "a21026": {"name": "SO2", "unit": "mg/m³", "limit": 35},
            "a21002": {"name": "NOx", "unit": "mg/m³", "limit": 50},
            "a34013": {"name": "颗粒物", "unit": "mg/m³", "limit": 10},
            "a19001": {"name": "烟气黑度", "unit": "级", "limit": 1},
            "a01006": {"name": "氧含量", "unit": "%", "reference": 6},
            "a00000": {"name": "烟气流速", "unit": "m/s", "reference": None},
            "a01007": {"name": "烟气温度", "unit": "℃", "reference": None},
        },
    },
    "noise": {
        "name": "噪声",
        "standards": "《工业企业厂界环境噪声排放标准》(GB 12348-2008)、《环境噪声监测技术规范 噪声测量值修正》(HJ 706-2014)、《声环境质量标准》(GB 3096-2008)",
        "terms": "昼间/夜间限值、等效连续A声级(Leq)、瞬时声级、频发噪声、偶发噪声、背景噪声扣除、脉冲噪声修正、厂界测点",
        "suggestions": "排查高噪声设备运行时间安排、检查隔声屏障完整性、区分厂界外背景噪声、核实夜间生产计划、评估设备减振措施效果",
        "typical_pollutants": {
            "l01001": {"name": "昼间等效声级", "unit": "dB(A)", "limit": 65},
            "l01002": {"name": "夜间等效声级", "unit": "dB(A)", "limit": 55},
            "l01003": {"name": "最大声级", "unit": "dB(A)", "limit": 75},
        },
        "zone_limits": {
            "1类": {"day": 55, "night": 45},
            "2类": {"day": 60, "night": 50},
            "3类": {"day": 65, "night": 55},
            "4类": {"day": 70, "night": 55},
        },
    },
    "soil": {
        "name": "土壤",
        "standards": "《土壤环境质量 建设用地土壤污染风险管控标准》(GB 36600-2018)、《土壤环境质量 农用地土壤污染风险管控标准》(GB 15618-2018)",
        "terms": "重金属富集系数、酸碱度(pH)、有机物渗透、淋溶作用、风险筛选值、管制值、土壤容重、孔隙度、阳离子交换量(CEC)",
        "suggestions": "检查防渗层完整性、排查原料堆场跑冒滴漏、核实地下水位变化、评估植物修复效果、取样复测确认趋势",
        "typical_pollutants": {
            "s03001": {"name": "镉", "unit": "mg/kg", "limit": 20},
            "s03002": {"name": "汞", "unit": "mg/kg", "limit": 8},
            "s03003": {"name": "砷", "unit": "mg/kg", "limit": 20},
            "s03004": {"name": "铅", "unit": "mg/kg", "limit": 400},
            "s03005": {"name": "铬", "unit": "mg/kg", "limit": 150},
            "s03006": {"name": "铜", "unit": "mg/kg", "limit": 2000},
            "s03007": {"name": "锌", "unit": "mg/kg", "limit": 2000},
            "s03008": {"name": "镍", "unit": "mg/kg", "limit": 150},
        },
    },
}


# =============================================================================
# 污染物代码前缀到领域的映射
# =============================================================================

POLLUTANT_PREFIX_DOMAIN_MAP: dict[str, str] = {
    "w": "water",  # 水质
    "a": "air",  # 大气
    "l": "noise",  # 噪声 (L = Level)
    "s": "soil",  # 土壤
    "n": "noise",  # 噪声 (备用)
}


# =============================================================================
# 通用专家诊断 Prompt 模板
# =============================================================================

EXPERT_DIAGNOSIS_TEMPLATE = """
# Role (角色设定)
你是由【EcoMind】开发的"首席环保数据分析师"。你拥有 20 年环境工程经验，精通{domain_standards}及相关国家排放标准。

你的分析必须具备{monitor_type}领域的专业深度：
1. **行业术语**：分析时必须熟练使用"{domain_terms}"等专业词汇。
2. **客观冷静**：完全基于数据说话，拒绝模棱两可的推测。
3. **合规导向**：时刻关注{monitor_type}排放的合规风险。

# Context (背景信息)
- 监测类型：{monitor_type}
- 设备名称：{device_name}
- 监测因子：{pollutant_name}
- 报告日期：{report_date}

# Observation (监测数据摘要)
以下是该设备今日的运行核心指标：
```json
{{
  "avg_value": "{avg_val} {unit}",
  "max_value": "{max_val} {unit} (出现于 {peak_time})",
  "min_value": "{min_val} {unit}",
  "alarm_count": "{alarm_count} 次",
  "compliance_status": "{compliance_status}",
  "trend_description": "{trend_desc}"
}}
```

# Constraints (严格约束 - 防幻觉机制)
1. **依据事实**：严禁编造 Observation 中未提供的数据。
2. **标准引用**：在判定异常时，必须依据{domain_standards}进行说明。
3. **数值敏感**：如果数据异常，必须使用"**风险**"等警示词并加粗。

# Task (任务目标)
请撰写《智能运维诊断日报》，包含以下章节（Markdown格式）：

## 1. 📊 运行综述
用简练的专业术语总结今日运行状态。

## 2. ⚠️ 异常诊断
- (若有异常)：结合趋势，分析可能的工艺原因（参考方向：{domain_suggestions}）。
- (若正常)：肯定当前的运维管理。

## 3. 🛠 运维建议
给出 3 条具体的、针对{monitor_type}设备的现场排查或优化步骤。

## 4. ⚖️ 合规风险评估
评估当前的排放是否存在被环保局处罚的风险。
"""


# =============================================================================
# 综合诊断 Prompt 模板 (多污染物)
# =============================================================================

COMPREHENSIVE_DIAGNOSIS_TEMPLATE = """
# Role (角色设定)
你是由【EcoMind】开发的"首席环保数据分析师"。你拥有 20 年环境工程经验，精通{domain_standards}及相关国家排放标准。

你的分析必须具备{monitor_type}领域的专业深度：
1. **行业术语**：分析时必须熟练使用"{domain_terms}"等专业词汇。
2. **客观冷静**：完全基于数据说话，拒绝模棱两可的推测。
3. **合规导向**：时刻关注{monitor_type}排放的合规风险。
4. **综合视角**：从多个污染物指标间的关联性进行整体分析。

# Context (背景信息)
- 监测类型：{monitor_type}
- 设备名称：{device_name}
- 设备编号：{device_id}
- 报告日期：{report_date}
- 监测因子数量：{pollutant_count} 种

# Observation (监测数据全览)
以下是该设备今日所有监测因子的运行数据：

## 📊 综合统计
- 总数据点数：{total_data_points}
- 超标因子数：{over_limit_pollutant_count} 种
- 总超标次数：{total_over_limit_count} 次
- 高波动因子：{high_volatility_count} 种

## 📋 各因子详细数据
```json
{pollutants_json}
```

## ⚠️ 异常因子汇总
{anomaly_summary}

# Constraints (严格约束 - 防幻觉机制)
1. **依据事实**：严禁编造 Observation 中未提供的数据。
2. **标准引用**：在判定异常时，必须依据{domain_standards}进行说明。
3. **数值敏感**：如果数据异常，必须使用"**风险**"等警示词并加粗。
4. **关联分析**：必须从污染物间的关联性角度进行分析（如 COD 与 BOD 关系、重金属间的协同变化等）。

# Task (任务目标)
请撰写《智能运维诊断日报》，包含以下章节（Markdown格式）：

## 1. 📊 运行综述
- 用简练的专业术语总结今日整体运行状态
- 列出需要重点关注的污染因子

## 2. ⚠️ 异常诊断
- 分析各超标/高波动因子的可能工艺原因
- 分析污染物之间的关联性（如：COD超标是否伴随氨氮上升？重金属指标是否协同变化？）
- 结合趋势，判断是偶发性异常还是系统性问题
- 参考方向：{domain_suggestions}

## 3. 🛠 运维建议
给出 3-5 条具体的、针对{monitor_type}设备的现场排查或优化步骤，针对当前检测到的问题优先级排序。

## 4. ⚖️ 合规风险评估
- 评估当前的排放是否存在被环保局处罚的风险
- 指出哪些因子需要优先整改
- 给出合规风险等级（低/中/高/紧急）

## 5. 📈 趋势研判
基于当日数据特征，预判未来 24-48 小时可能出现的变化趋势和需要提前准备的应对措施。
"""


# =============================================================================
# 简洁对话 Prompt 模板（用于交互式问答）
# =============================================================================

CHAT_SYSTEM_PROMPT = """你是 EcoMind 环保智能助手，专注于{monitor_type}监测领域。

你的专业背景：
- 熟悉{domain_standards}
- 精通{domain_terms}等专业术语
- 能够提供{domain_suggestions}等实用建议

请用专业但易懂的语言回答问题。回答要简洁、准确、有依据。"""


# =============================================================================
# 数据异常告警 Prompt 模板
# =============================================================================

ALARM_ANALYSIS_TEMPLATE = """
# 告警分析任务

## 背景
设备【{device_name}】的{pollutant_name}监测因子触发告警。

## 告警详情
- 告警时间：{alarm_time}
- 当前值：{current_value} {unit}
- 阈值：{threshold_value} {unit}
- 超标率：{exceed_rate}%

## 参考标准
{domain_standards}

## 请分析
1. 可能的原因（参考：{domain_suggestions}）
2. 紧急程度评估（低/中/高/紧急）
3. 建议的处置措施
"""


# =============================================================================
# 辅助函数
# =============================================================================


def get_domain_from_device_type(device_type: str) -> str:
    """
    根据设备类型获取领域标识。

    Args:
        device_type: 设备类型 (water/air/noise/soil)

    Returns:
        领域标识
    """
    device_type_lower = device_type.lower()
    if device_type_lower in DOMAIN_KNOWLEDGE:
        return device_type_lower
    return "water"  # 默认返回水质


def get_domain_from_pollutant_code(pollutant_code: str) -> str:
    """
    根据污染物代码推断领域。

    Args:
        pollutant_code: 污染物代码（如 w01018, a21026）

    Returns:
        领域标识
    """
    if not pollutant_code:
        return "water"

    prefix = pollutant_code[0].lower()
    return POLLUTANT_PREFIX_DOMAIN_MAP.get(prefix, "water")


def get_domain_knowledge(domain: str) -> dict[str, Any]:
    """
    获取指定领域的知识库。

    Args:
        domain: 领域标识 (water/air/noise/soil)

    Returns:
        领域知识字典
    """
    return DOMAIN_KNOWLEDGE.get(domain.lower(), DOMAIN_KNOWLEDGE["water"])


def get_pollutant_info(domain: str, pollutant_code: str) -> dict[str, Any]:
    """
    获取污染物信息。

    优先从领域知识库查找，若未找到则从完整污染物库查找。

    Args:
        domain: 领域标识
        pollutant_code: 污染物代码

    Returns:
        污染物信息字典
    """
    # 首先尝试从领域知识库查找
    knowledge = get_domain_knowledge(domain)
    typical = knowledge.get("typical_pollutants", {})
    if pollutant_code in typical:
        return typical[pollutant_code]

    # 若未找到，从完整污染物库查找（用于重金属等扩展指标）
    from app.core.pollutant_library import get_pollutant_info as lib_get_info
    lib_info = lib_get_info(pollutant_code)
    if lib_info:
        return {
            "name": lib_info["name"],
            "unit": lib_info["unit"],
            "limit": None,  # 限值需单独配置
        }

    # 最终回退：返回编码本身
    return {"name": pollutant_code, "unit": "", "limit": None}


def build_expert_diagnosis_prompt(
    device_type: str,
    device_name: str,
    pollutant_code: str,
    pollutant_name: str,
    report_date: str,
    avg_val: float,
    max_val: float,
    min_val: float,
    peak_time: str,
    alarm_count: int,
    compliance_status: str,
    trend_desc: str,
    unit: str = "",
) -> str:
    """
    构建专家诊断 Prompt。

    Args:
        device_type: 设备类型
        device_name: 设备名称
        pollutant_code: 污染物代码
        pollutant_name: 污染物名称
        report_date: 报告日期
        avg_val: 平均值
        max_val: 最大值
        min_val: 最小值
        peak_time: 峰值时间
        alarm_count: 告警次数
        compliance_status: 合规状态
        trend_desc: 趋势描述
        unit: 单位

    Returns:
        格式化后的 Prompt 字符串
    """
    # 确定领域
    domain = get_domain_from_device_type(device_type)
    if not domain or domain not in DOMAIN_KNOWLEDGE:
        domain = get_domain_from_pollutant_code(pollutant_code)

    # 获取领域知识
    knowledge = get_domain_knowledge(domain)

    # 格式化 Prompt
    prompt = EXPERT_DIAGNOSIS_TEMPLATE.format(
        domain_standards=knowledge["standards"],
        domain_terms=knowledge["terms"],
        domain_suggestions=knowledge["suggestions"],
        monitor_type=knowledge["name"],
        device_name=device_name,
        pollutant_name=pollutant_name,
        report_date=report_date,
        avg_val=avg_val,
        max_val=max_val,
        min_val=min_val,
        peak_time=peak_time,
        alarm_count=alarm_count,
        compliance_status=compliance_status,
        trend_desc=trend_desc,
        unit=unit,
    )

    return prompt


def build_chat_system_prompt(device_type: str | None = None, pollutant_code: str | None = None) -> str:
    """
    构建对话系统 Prompt。

    Args:
        device_type: 设备类型（可选）
        pollutant_code: 污染物代码（可选）

    Returns:
        格式化后的系统 Prompt
    """
    # 确定领域
    domain = "water"  # 默认
    if device_type:
        domain = get_domain_from_device_type(device_type)
    elif pollutant_code:
        domain = get_domain_from_pollutant_code(pollutant_code)

    knowledge = get_domain_knowledge(domain)

    return CHAT_SYSTEM_PROMPT.format(
        monitor_type=knowledge["name"],
        domain_standards=knowledge["standards"],
        domain_terms=knowledge["terms"],
        domain_suggestions=knowledge["suggestions"],
    )


def build_alarm_analysis_prompt(
    device_name: str,
    device_type: str,
    pollutant_code: str,
    pollutant_name: str,
    alarm_time: str,
    current_value: float,
    threshold_value: float,
    unit: str = "",
) -> str:
    """
    构建告警分析 Prompt。

    Args:
        device_name: 设备名称
        device_type: 设备类型
        pollutant_code: 污染物代码
        pollutant_name: 污染物名称
        alarm_time: 告警时间
        current_value: 当前值
        threshold_value: 阈值
        unit: 单位

    Returns:
        格式化后的 Prompt
    """
    domain = get_domain_from_device_type(device_type)
    knowledge = get_domain_knowledge(domain)

    exceed_rate = ((current_value - threshold_value) / threshold_value * 100) if threshold_value > 0 else 0

    return ALARM_ANALYSIS_TEMPLATE.format(
        device_name=device_name,
        pollutant_name=pollutant_name,
        alarm_time=alarm_time,
        current_value=current_value,
        threshold_value=threshold_value,
        exceed_rate=f"{exceed_rate:.1f}",
        unit=unit,
        domain_standards=knowledge["standards"],
        domain_suggestions=knowledge["suggestions"],
    )


def build_comprehensive_diagnosis_prompt(
    device_id: str,
    device_name: str,
    report_date: str,
    pollutants_stats: list[dict[str, Any]],
    total_data_points: int,
    domain: str = "water",
) -> str:
    """
    构建综合诊断 Prompt（多污染物分析）。

    Args:
        device_id: 设备 ID
        device_name: 设备名称
        report_date: 报告日期
        pollutants_stats: 各污染物的统计数据列表
        total_data_points: 总数据点数
        domain: 领域标识 (water/air/noise/soil)

    Returns:
        格式化后的综合诊断 Prompt 字符串
    """
    import json

    # 获取领域知识
    knowledge = get_domain_knowledge(domain)

    # 统计综合指标
    over_limit_pollutant_count = sum(
        1 for p in pollutants_stats if p.get("over_limit_count", 0) > 0
    )
    total_over_limit_count = sum(
        p.get("over_limit_count", 0) for p in pollutants_stats
    )
    high_volatility_count = sum(
        1 for p in pollutants_stats if p.get("volatility", 0) > 20
    )

    # 构建污染物详细数据 JSON
    pollutants_detail = []
    for p in pollutants_stats:
        # 获取污染物名称
        pollutant_info = get_pollutant_info(domain, p["pollutant_code"])
        detail = {
            "代码": p["pollutant_code"],
            "名称": pollutant_info.get("name", p["pollutant_code"]),
            "单位": pollutant_info.get("unit", ""),
            "均值": p["avg_val"],
            "最大值": p["max_val"],
            "最小值": p["min_val"],
            "峰值时间": p.get("peak_time", "-"),
            "波动率": f"{p.get('volatility', 0):.1f}%",
            "超标次数": p.get("over_limit_count", 0),
            "阈值": p.get("threshold_value"),
            "趋势描述": p.get("trend_description", ""),
        }
        pollutants_detail.append(detail)

    pollutants_json = json.dumps(pollutants_detail, ensure_ascii=False, indent=2)

    # 构建异常因子汇总
    anomaly_lines = []
    for p in pollutants_stats:
        issues = []
        if p.get("over_limit_count", 0) > 0:
            issues.append(f"超标 {p['over_limit_count']} 次")
        if p.get("volatility", 0) > 20:
            issues.append(f"波动率 {p['volatility']:.1f}%")

        if issues:
            pollutant_info = get_pollutant_info(domain, p["pollutant_code"])
            p_name = pollutant_info.get("name", p["pollutant_code"])
            anomaly_lines.append(
                f"- **{p_name}** ({p['pollutant_code']}): {', '.join(issues)}"
            )

    if anomaly_lines:
        anomaly_summary = "\n".join(anomaly_lines)
    else:
        anomaly_summary = "无异常因子，所有指标正常。"

    # 格式化 Prompt
    prompt = COMPREHENSIVE_DIAGNOSIS_TEMPLATE.format(
        domain_standards=knowledge["standards"],
        domain_terms=knowledge["terms"],
        domain_suggestions=knowledge["suggestions"],
        monitor_type=knowledge["name"],
        device_name=device_name,
        device_id=device_id,
        report_date=report_date,
        pollutant_count=len(pollutants_stats),
        total_data_points=total_data_points,
        over_limit_pollutant_count=over_limit_pollutant_count,
        total_over_limit_count=total_over_limit_count,
        high_volatility_count=high_volatility_count,
        pollutants_json=pollutants_json,
        anomaly_summary=anomaly_summary,
    )

    return prompt
