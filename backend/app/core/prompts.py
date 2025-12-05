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
# 行业排放标准知识库（用于 AI Prompt 注入）
# =============================================================================

INDUSTRY_STANDARD_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "municipal_wastewater": {
        "name": "城镇污水处理厂",
        "standard": "GB 18918-2002",
        "standard_name": "城镇污水处理厂污染物排放标准",
        "limits": {
            "一级A": {"COD": 50, "BOD5": 10, "SS": 10, "氨氮": 5, "总氮": 15, "总磷": 0.5},
            "一级B": {"COD": 60, "BOD5": 20, "SS": 20, "氨氮": 8, "总氮": 20, "总磷": 1.0},
            "二级": {"COD": 100, "BOD5": 30, "SS": 30, "氨氮": 25, "总氮": None, "总磷": 3.0},
        },
        "key_points": "关注出水氨氮与总氮的脱氮效率，生化系统的碳氮比是否合理；磷的去除需关注化学除磷药剂投加量",
        "typical_issues": "进水负荷波动、碳源不足导致脱氮效率下降、污泥龄过长或过短",
    },
    "electroplating": {
        "name": "电镀工业",
        "standard": "GB 21900-2008",
        "standard_name": "电镀污染物排放标准",
        "limits": {
            "表1": {"总铬": 1.0, "六价铬": 0.2, "总镍": 0.5, "总镉": 0.05, "总银": 0.3, "总铅": 0.2, "总汞": 0.005},
            "表2": {"总铜": 0.5, "总锌": 1.5, "总铁": None, "COD": 80, "氨氮": 15},
        },
        "key_points": "重金属为核心管控指标，六价铬需特别关注；需要完善的分流收集系统和针对性处理工艺",
        "typical_issues": "重金属混排导致处理效率下降、还原剂投加不足导致六价铬超标、污泥含重金属需危废处理",
    },
    "textile_dyeing": {
        "name": "纺织染整工业",
        "standard": "GB 4287-2012",
        "standard_name": "纺织染整工业水污染物排放标准",
        "limits": {
            "直排": {"COD": 80, "BOD5": 20, "SS": 50, "氨氮": 10, "总氮": 15, "总磷": 0.5, "色度": 50},
            "间排": {"COD": 200, "BOD5": 50, "SS": 100, "氨氮": 20, "总氮": 30, "总磷": 1.5, "色度": 80},
        },
        "key_points": "色度是纺织废水的特征污染物，需关注脱色工艺；COD与色度往往呈正相关",
        "typical_issues": "染料种类变化导致处理效果波动、色度去除率不稳定、难降解有机物积累",
    },
    "thermal_power": {
        "name": "火电厂",
        "standard": "GB 13223-2011",
        "standard_name": "火电厂大气污染物排放标准",
        "limits": {
            "一般地区": {"SO2": 100, "NOx": 100, "颗粒物": 30, "汞及其化合物": 0.03},
            "重点地区": {"SO2": 50, "NOx": 50, "颗粒物": 20, "汞及其化合物": 0.03},
        },
        "key_points": "脱硫效率与浆液品质密切相关；SCR脱硝需关注催化剂活性和氨逃逸；布袋除尘压差反映滤袋状态",
        "typical_issues": "脱硫塔结垢、SCR催化剂失活、布袋破损、CEMS数据漂移",
    },
    "pharmaceutical": {
        "name": "制药工业",
        "standard": "GB 21903-2008",
        "standard_name": "制药工业水污染物排放标准",
        "limits": {
            "发酵类": {"COD": 120, "BOD5": 30, "SS": 50, "氨氮": 25, "总氮": 35, "总磷": 1.0},
            "化学合成类": {"COD": 150, "BOD5": 30, "SS": 50, "氨氮": 25, "总氮": 35, "总磷": 1.0},
        },
        "key_points": "制药废水成分复杂，可生化性差；抗生素等特征污染物可能抑制生化系统",
        "typical_issues": "间歇排放导致冲击负荷、有毒物质抑制微生物活性、难降解有机物需要预处理",
    },
    "paper_making": {
        "name": "造纸工业",
        "standard": "GB 3544-2008",
        "standard_name": "制浆造纸工业水污染物排放标准",
        "limits": {
            "制浆": {"COD": 90, "BOD5": 20, "SS": 30, "氨氮": 8, "总磷": 0.8, "AOX": 8},
            "造纸": {"COD": 90, "BOD5": 20, "SS": 30, "氨氮": 8, "总磷": 0.8},
        },
        "key_points": "黑液回收是制浆废水处理的关键；AOX（可吸附有机卤化物）是制浆废水的特征污染物",
        "typical_issues": "黑液泄漏、高浓度COD冲击、纤维堵塞生化系统",
    },
    "petrochemical": {
        "name": "石油化工",
        "standard": "GB 31571-2015",
        "standard_name": "石油化学工业污染物排放标准",
        "limits": {
            "直排": {"COD": 60, "BOD5": 20, "SS": 30, "氨氮": 8, "总氮": 20, "石油类": 3.0, "挥发酚": 0.3},
            "间排": {"COD": 200, "BOD5": 50, "SS": 100, "氨氮": 25, "总氮": 40, "石油类": 10, "挥发酚": 0.5},
        },
        "key_points": "石油类和挥发酚是特征污染物；废水含油需要预处理隔油或气浮",
        "typical_issues": "油类乳化导致分离困难、酚类抑制生化系统、有机硫化物影响处理效果",
    },
    "steel": {
        "name": "钢铁工业",
        "standard": "GB 13456-2012",
        "standard_name": "钢铁工业水污染物排放标准",
        "limits": {
            "直排": {"COD": 50, "SS": 30, "氨氮": 5, "总氮": 15, "石油类": 3.0, "总铁": 2.0, "总锌": 1.0},
            "间排": {"COD": 100, "SS": 70, "氨氮": 15, "总氮": 30, "石油类": 8.0, "总铁": 5.0, "总锌": 3.0},
        },
        "key_points": "重金属和悬浮物是主要污染物；酸洗废水需要中和处理；含油废水需要隔油预处理",
        "typical_issues": "酸碱度波动大、重金属混排、悬浮物沉淀效果差",
    },
    "cement": {
        "name": "水泥工业",
        "standard": "GB 4915-2013",
        "standard_name": "水泥工业大气污染物排放标准",
        "limits": {
            "窑及窑尾": {"颗粒物": 30, "NOx": 400, "SO2": 200, "氟化物": 3.0},
            "破碎机及其他": {"颗粒物": 20},
        },
        "key_points": "NOx控制是水泥窑的主要挑战；SNCR/SCR脱硝效率受温度窗口影响",
        "typical_issues": "窑况波动影响脱硝效率、粉尘泄漏、CEMS数据可靠性",
    },
    "other": {
        "name": "其他（通用标准）",
        "standard": "GB 8978-1996",
        "standard_name": "污水综合排放标准",
        "limits": {
            "一级": {"COD": 100, "BOD5": 20, "SS": 70, "氨氮": 15, "总磷": 0.5, "石油类": 5.0},
            "二级": {"COD": 150, "BOD5": 30, "SS": 150, "氨氮": 25, "总磷": 1.0, "石油类": 10},
            "三级": {"COD": 500, "BOD5": 300, "SS": 400, "氨氮": None, "总磷": None, "石油类": 20},
        },
        "key_points": "综合排放标准适用于未制定行业标准的行业，限值相对宽松",
        "typical_issues": "需根据实际排放去向（直排/间排）确定执行标准级别",
    },
}


def get_industry_knowledge(industry_type: str | None) -> dict[str, Any] | None:
    """
    获取指定行业的标准知识。

    Args:
        industry_type: 行业类型代码

    Returns:
        行业标准知识字典，若未找到则返回 None
    """
    if not industry_type:
        return None
    return INDUSTRY_STANDARD_KNOWLEDGE.get(industry_type)


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
{industry_context}

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

## 📈 小时级统计趋势
以下为各污染物的小时级聚合数据（均值/峰值/谷值），用于识别日内变化规律：
```
{hourly_stats_text}
```

## ⚠️ 异常因子汇总
{anomaly_summary}

{anomaly_events_text}

# Constraints (严格约束 - 防幻觉机制)
1. **依据事实**：严禁编造 Observation 中未提供的数据。
2. **标准引用**：在判定异常时，必须依据{domain_standards}进行说明。
3. **数值敏感**：如果数据异常，必须使用"**风险**"等警示词并加粗。
4. **关联分析**：必须从污染物间的关联性角度进行分析（如 COD 与 BOD 关系、重金属间的协同变化等）。
5. **事件关注**：重点关注异常事件摘要中的超标点、故障点和 AI 突变点。
6. **趋势依据**：趋势研判必须明确引用小时级数据作为预测依据。

# Task (任务目标)
请撰写《智能运维诊断日报》，包含以下章节（Markdown格式）：

## 1. 📊 运行综述
- 用简练的专业术语总结今日整体运行状态
- 列出需要重点关注的污染因子
- 概述小时级变化趋势特征（如：上午平稳、下午攀升等）

## 2. ⚠️ 异常诊断
**必须按以下三类事件分别诊断**（若某类无事件可注明"无"）：

### 2.1 🔴 超标事件诊断
- 逐一分析每个超标时刻的情况
- 说明超标时的数值、超标幅度、持续时间
- 结合前后小时数据，分析可能的工艺原因

### 2.2 🟠 故障/异常时段诊断
- 分析设备故障、数据缺失、通讯异常等时段
- 评估故障对监测数据完整性的影响
- 判断是设备问题还是工艺问题

### 2.3 🟡 AI 突变点诊断
- 分析 AI 检测到的数据突变事件
- 说明突变幅度、发生时刻
- 结合污染物关联性，推断可能原因（如：COD 突升是否伴随 pH 波动？）

### 2.4 🔗 多因子关联分析
- 分析污染物之间的协同变化关系
- 判断是偶发性异常还是系统性问题
- 参考方向：{domain_suggestions}

## 3. 🛠 运维建议
给出 3-5 条具体的、针对{monitor_type}设备的现场排查或优化步骤，按问题紧急程度排序：
- 【紧急】需立即处理的问题
- 【重要】需当日关注的问题
- 【常规】日常优化建议

## 4. ⚖️ 合规风险评估
- 评估当前的排放是否存在被环保局处罚的风险
- **必须依据执行标准进行判定**{industry_standard_hint}
- 指出哪些因子需要优先整改
- 给出合规风险等级（低/中/高/紧急）及判定依据

## 5. 📈 趋势研判
**必须基于小时级数据进行有依据的预测**：

### 5.1 数据依据
- 明确引用今日的小时级趋势规律（如：XX 因子在 14:00-18:00 呈上升趋势，峰值出现在 XX:00）
- 指出关键时段的数据变化特征

### 5.2 未来 24-48 小时预测
- 基于今日趋势规律，预判明日可能的高风险时段
- 若今日有超标/突变，预判是否可能再次发生

### 5.3 预防性措施
- 针对预测的风险点，给出提前准备的应对措施
- 建议重点监控的时段和因子
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
    hourly_stats_text: str = "",
    anomaly_events_text: str = "",
    industry_type: str | None = None,
    national_standard: str | None = None,
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
        hourly_stats_text: 小时级统计文本（格式：14:00, COD: 均值50/峰值200/谷值20）
        anomaly_events_text: 异常事件摘要文本
        industry_type: 行业类型代码（可选）
        national_standard: 执行标准号（可选）

    Returns:
        格式化后的综合诊断 Prompt 字符串
    """
    import json

    # 获取领域知识
    knowledge = get_domain_knowledge(domain)

    # 获取行业标准知识
    industry_knowledge = get_industry_knowledge(industry_type)

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

    # 构建污染物详细数据 JSON（不包含 hourly_stats 和 anomaly_events 以节省 Token）
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

    # 如果没有提供小时级统计文本，则使用默认值
    if not hourly_stats_text:
        hourly_stats_text = "无小时级统计数据"

    # 如果没有提供异常事件文本，则使用默认值
    if not anomaly_events_text:
        anomaly_events_text = "【异常事件摘要】\n无异常事件"

    # 构建行业上下文信息
    industry_context = ""
    industry_standard_hint = ""
    if industry_knowledge:
        industry_context = f"""
## 🏭 行业信息
- 所属行业：{industry_knowledge["name"]}
- 执行标准：{national_standard or industry_knowledge["standard"]}（{industry_knowledge["standard_name"]}）
- 行业关键点：{industry_knowledge["key_points"]}
- 常见问题：{industry_knowledge["typical_issues"]}

### 排放限值参考
"""
        # 添加限值表
        limits = industry_knowledge.get("limits", {})
        for level, limit_dict in limits.items():
            limit_items = [f"{k}: {v}" for k, v in limit_dict.items() if v is not None]
            industry_context += f"- {level}：{', '.join(limit_items)}\n"

        industry_standard_hint = f"（本设备执行 {national_standard or industry_knowledge['standard']}）"
    elif national_standard:
        industry_context = f"\n- 执行标准：{national_standard}"
        industry_standard_hint = f"（本设备执行 {national_standard}）"

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
        hourly_stats_text=hourly_stats_text,
        anomaly_summary=anomaly_summary,
        anomaly_events_text=anomaly_events_text,
        industry_context=industry_context,
        industry_standard_hint=industry_standard_hint,
    )

    return prompt
