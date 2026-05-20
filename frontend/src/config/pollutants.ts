/**
 * HJ 212-2017/2025 监测污染物字典
 * 与后端 POLLUTANT_MAP 保持一致
 */

export interface PollutantInfo {
  name: string       // 中文名称
  unit: string       // 计量单位
  precision: number  // 小数位数
  category?: string  // 分类
}

// 完整的污染物字典
export const POLLUTANT_MAP: Record<string, PollutantInfo> = {
  // =========================================================================
  // 常规五参数 & 物理指标
  // =========================================================================
  'w00000': { name: '瞬时流量', unit: 'm³/h', precision: 2, category: 'physical' },
  'w00001': { name: '累计流量', unit: 'm³', precision: 2, category: 'physical' },
  'w01001': { name: 'pH值', unit: '无量纲', precision: 2, category: 'physical' },
  'w01010': { name: '水温', unit: '℃', precision: 1, category: 'physical' },
  'w01003': { name: '浊度', unit: 'NTU', precision: 1, category: 'physical' },
  'w01014': { name: '电导率', unit: 'μS/cm', precision: 1, category: 'physical' },
  'w01009': { name: '溶解氧', unit: 'mg/L', precision: 2, category: 'physical' },
  'w01008': { name: '色度', unit: '度', precision: 0, category: 'physical' },
  'w01002': { name: '透明度', unit: 'cm', precision: 0, category: 'physical' },
  'w01012': { name: '氧化还原电位', unit: 'mV', precision: 1, category: 'physical' },
  'w01004': { name: '悬浮物', unit: 'mg/L', precision: 1, category: 'physical' },

  // =========================================================================
  // 有机物 & 耗氧量指标
  // =========================================================================
  'w01018': { name: 'COD', unit: 'mg/L', precision: 2, category: 'organic' },
  'w01019': { name: '高锰酸盐指数', unit: 'mg/L', precision: 2, category: 'organic' },
  'w01017': { name: 'BOD5', unit: 'mg/L', precision: 2, category: 'organic' },
  'w01020': { name: 'TOC', unit: 'mg/L', precision: 2, category: 'organic' },
  'w23002': { name: '挥发酚', unit: 'mg/L', precision: 4, category: 'organic' },
  'w22001': { name: '石油类', unit: 'mg/L', precision: 3, category: 'organic' },
  'w23001': { name: '动植物油', unit: 'mg/L', precision: 2, category: 'organic' },
  'w19001': { name: '阴离子表面活性剂', unit: 'mg/L', precision: 3, category: 'organic' },

  // =========================================================================
  // 营养盐 (氮磷系列)
  // =========================================================================
  'w21003': { name: '氨氮', unit: 'mg/L', precision: 3, category: 'nitrogen_phosphorus' },
  'w21001': { name: '总氮', unit: 'mg/L', precision: 2, category: 'nitrogen_phosphorus' },
  'w21011': { name: '总磷', unit: 'mg/L', precision: 3, category: 'nitrogen_phosphorus' },
  'w21006': { name: '亚硝酸盐氮', unit: 'mg/L', precision: 3, category: 'nitrogen_phosphorus' },
  'w21007': { name: '硝酸盐氮', unit: 'mg/L', precision: 2, category: 'nitrogen_phosphorus' },
  'w21023': { name: '磷酸盐', unit: 'mg/L', precision: 3, category: 'nitrogen_phosphorus' },
  'w21002': { name: '凯氏氮', unit: 'mg/L', precision: 2, category: 'nitrogen_phosphorus' },
  'w21004': { name: '游离氨', unit: 'mg/L', precision: 3, category: 'nitrogen_phosphorus' },
  'w21019': { name: '正磷酸盐', unit: 'mg/L', precision: 3, category: 'nitrogen_phosphorus' },

  // =========================================================================
  // 毒性阴离子
  // =========================================================================
  'w21017': { name: '氟化物', unit: 'mg/L', precision: 3, category: 'toxic_anions' },
  'w21016': { name: '氰化物', unit: 'mg/L', precision: 4, category: 'toxic_anions' },
  'w21022': { name: '硫化物', unit: 'mg/L', precision: 3, category: 'toxic_anions' },
  'w21038': { name: '硫酸盐', unit: 'mg/L', precision: 1, category: 'toxic_anions' },
  'w21039': { name: '氯化物', unit: 'mg/L', precision: 1, category: 'toxic_anions' },

  // =========================================================================
  // 重金属 - 一类 (毒性最强，限值最低)
  // =========================================================================
  'w20111': { name: '总汞', unit: 'mg/L', precision: 5, category: 'heavy_metals_class1' },
  'w20115': { name: '总镉', unit: 'mg/L', precision: 5, category: 'heavy_metals_class1' },
  'w20117': { name: '六价铬', unit: 'mg/L', precision: 4, category: 'heavy_metals_class1' },
  'w20119': { name: '总砷', unit: 'mg/L', precision: 4, category: 'heavy_metals_class1' },
  'w20120': { name: '总铅', unit: 'mg/L', precision: 4, category: 'heavy_metals_class1' },

  // =========================================================================
  // 重金属 - 二类
  // =========================================================================
  'w20116': { name: '总铬', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },
  'w20122': { name: '总铜', unit: 'mg/L', precision: 3, category: 'heavy_metals_class2' },
  'w20123': { name: '总锌', unit: 'mg/L', precision: 3, category: 'heavy_metals_class2' },
  'w20121': { name: '总镍', unit: 'mg/L', precision: 3, category: 'heavy_metals_class2' },
  'w20124': { name: '总锰', unit: 'mg/L', precision: 3, category: 'heavy_metals_class2' },
  'w20125': { name: '总铁', unit: 'mg/L', precision: 2, category: 'heavy_metals_class2' },
  'w20126': { name: '总银', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },
  'w20127': { name: '总铝', unit: 'mg/L', precision: 3, category: 'heavy_metals_class2' },
  'w20128': { name: '总钡', unit: 'mg/L', precision: 3, category: 'heavy_metals_class2' },
  'w20129': { name: '总铍', unit: 'mg/L', precision: 5, category: 'heavy_metals_class2' },
  'w20130': { name: '总铋', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },
  'w20038': { name: '总钴', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },
  'w20141': { name: '总锑', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },
  'w20092': { name: '总锡', unit: 'mg/L', precision: 3, category: 'heavy_metals_class2' },
  'w20131': { name: '总硒', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },
  'w20023': { name: '总铊', unit: 'mg/L', precision: 5, category: 'heavy_metals_class2' },
  'w20101': { name: '总钒', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },
  'w20113': { name: '总钼', unit: 'mg/L', precision: 4, category: 'heavy_metals_class2' },

  // =========================================================================
  // 有机污染物
  // =========================================================================
  'w23003': { name: '苯', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w23004': { name: '甲苯', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w23005': { name: '乙苯', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w23006': { name: '二甲苯', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w23007': { name: '苯乙烯', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w24001': { name: '苯并芘', unit: 'μg/L', precision: 4, category: 'organic_pollutants' },
  'w25001': { name: '三氯甲烷', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w25002': { name: '四氯化碳', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w25038': { name: '三氯乙烯', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },
  'w25039': { name: '四氯乙烯', unit: 'mg/L', precision: 4, category: 'organic_pollutants' },

  // =========================================================================
  // 农药类
  // =========================================================================
  'w33001': { name: '六六六', unit: 'mg/L', precision: 6, category: 'pesticides' },
  'w33007': { name: '滴滴涕', unit: 'mg/L', precision: 6, category: 'pesticides' },

  // =========================================================================
  // 微生物指标
  // =========================================================================
  'w02003': { name: '粪大肠菌群', unit: '个/L', precision: 0, category: 'microorganism' },
  'w02001': { name: '总大肠菌群', unit: '个/L', precision: 0, category: 'microorganism' },
  'w02008': { name: '细菌总数', unit: 'CFU/mL', precision: 0, category: 'microorganism' },

  // =========================================================================
  // 放射性指标
  // =========================================================================
  'w09001': { name: '总α放射性', unit: 'Bq/L', precision: 3, category: 'radioactive' },
  'w09002': { name: '总β放射性', unit: 'Bq/L', precision: 3, category: 'radioactive' },

  // =========================================================================
  // 其他综合指标
  // =========================================================================
  'w01016': { name: '总硬度', unit: 'mg/L', precision: 1, category: 'comprehensive' },
  'w01006': { name: '矿化度', unit: 'mg/L', precision: 0, category: 'comprehensive' },
  'w99001': { name: '叶绿素a', unit: 'mg/m³', precision: 2, category: 'comprehensive' },
  'w99002': { name: '藻密度', unit: '万个/L', precision: 0, category: 'comprehensive' },

  // =========================================================================
  // 大气/烟气监测指标
  // =========================================================================
  'a34013': { name: '烟尘(颗粒物)', unit: 'mg/m³', precision: 2, category: 'air_particulate' },
  'a21026': { name: '二氧化硫(SO2)', unit: 'mg/m³', precision: 2, category: 'air_gas' },
  'a21002': { name: '氮氧化物(NOx)', unit: 'mg/m³', precision: 2, category: 'air_gas' },
  'a21003': { name: '一氧化碳(CO)', unit: 'mg/m³', precision: 2, category: 'air_gas' },
  'a19001': { name: '烟气黑度', unit: '级', precision: 0, category: 'air_conditions' },
  'a01006': { name: '氧含量', unit: '%', precision: 2, category: 'air_conditions' },
  'a01007': { name: '烟气温度', unit: '℃', precision: 1, category: 'air_conditions' },
  'a01011': { name: '烟气流速', unit: 'm/s', precision: 2, category: 'air_conditions' },
  'a01012': { name: '烟气温度', unit: '℃', precision: 1, category: 'air_conditions' },
  'a01013': { name: '烟气压力', unit: 'kPa', precision: 2, category: 'air_conditions' },
  'a01014': { name: '烟气湿度', unit: '%', precision: 1, category: 'air_conditions' },
  'a34004': { name: 'PM2.5', unit: 'μg/m³', precision: 0, category: 'air_particulate' },
  'a34002': { name: 'PM10', unit: 'μg/m³', precision: 0, category: 'air_particulate' },
  'a21004': { name: '二氧化氮(NO2)', unit: 'μg/m³', precision: 0, category: 'air_gas' },
  'a05024': { name: '臭氧(O3)', unit: 'μg/m³', precision: 0, category: 'air_gas' },
  'a05001': { name: 'PM2.5', unit: 'μg/m³', precision: 0, category: 'air_particulate' },
  'a05002': { name: 'PM10', unit: 'μg/m³', precision: 0, category: 'air_particulate' },
}

export function normalizePollutantCode(code: string): string {
  return (code || '').trim().toLowerCase()
}

// 污染物分类定义
export const POLLUTANT_CATEGORIES: Record<string, { name: string; description: string }> = {
  physical: { name: '物理指标', description: '常规五参数及物理特性' },
  organic: { name: '有机物指标', description: 'COD、BOD等耗氧量指标' },
  nitrogen_phosphorus: { name: '营养盐', description: '氮磷系列指标' },
  toxic_anions: { name: '毒性阴离子', description: '氟化物、氰化物等' },
  heavy_metals_class1: { name: '一类重金属', description: '汞、镉、铬、砷、铅' },
  heavy_metals_class2: { name: '二类重金属', description: '铜、锌、镍等' },
  organic_pollutants: { name: '有机污染物', description: '苯系物、挥发性有机物' },
  pesticides: { name: '农药', description: '六六六、滴滴涕等' },
  microorganism: { name: '微生物', description: '大肠菌群、细菌' },
  radioactive: { name: '放射性', description: 'α、β放射性' },
  comprehensive: { name: '综合指标', description: '硬度、叶绿素等' },
  air_particulate: { name: '颗粒物', description: '烟尘、PM2.5、PM10' },
  air_gas: { name: '气态污染物', description: 'SO2、NOx、CO、NO2、O3' },
  air_conditions: { name: '烟气工况', description: '流速、温度、湿度、压力、含氧' },
}

// 常用指标快捷列表（用于默认显示）
// 污水监测数采仪常用指标：COD、氨氮、pH、总磷、总氮、TOC、温度、流量
export const COMMON_POLLUTANTS = [
  'w01018', // COD
  'w21003', // 氨氮
  'w01001', // pH
  'w21011', // 总磷
  'w21001', // 总氮
  'w01020', // TOC (有机碳)
  'w01010', // 水温
  'w00000', // 瞬时流量
]

// 大气监测常用指标：SO2、NOx、颗粒物、烟气黑度、含氧量、烟气温度
export const AIR_COMMON_POLLUTANTS = [
  'a21026', // SO2
  'a21002', // NOx
  'a34013', // 颗粒物
  'a19001', // 烟气黑度
  'a01006', // 含氧量
  'a01007', // 烟气温度
]

// 重金属指标列表（动态从字典中提取所有重金属）
export const HEAVY_METAL_POLLUTANTS = Object.entries(POLLUTANT_MAP)
  .filter(([_, info]) =>
    info.category === 'heavy_metals_class1' || info.category === 'heavy_metals_class2'
  )
  .map(([code]) => code)

// 注：电镀行业重金属指标已包含在 HEAVY_METAL_POLLUTANTS 中
// 氰化物(w21016)属于毒性阴离子类别，如需单独筛选请使用 toxic_anions 分类

/**
 * 获取污染物信息
 */
export function getPollutantInfo(code: string): PollutantInfo | undefined {
  const normalizedCode = normalizePollutantCode(code)
  return POLLUTANT_MAP[normalizedCode]
}

/**
 * 获取污染物名称
 */
export function getPollutantName(code: string): string {
  const normalizedCode = normalizePollutantCode(code)
  return POLLUTANT_MAP[normalizedCode]?.name || code
}

/**
 * 获取污染物单位
 */
export function getPollutantUnit(code: string): string {
  const normalizedCode = normalizePollutantCode(code)
  return POLLUTANT_MAP[normalizedCode]?.unit || 'mg/L'
}

/**
 * 格式化数值（根据精度）
 */
export function formatPollutantValue(code: string, value: number): string {
  const info = getPollutantInfo(code)
  const precision = info?.precision ?? 2
  return value.toFixed(precision)
}

/**
 * 获取所有污染物编码
 */
export function getAllPollutantCodes(): string[] {
  return Object.keys(POLLUTANT_MAP)
}

/**
 * 按分类获取污染物
 */
export function getPollutantsByCategory(category: string): { code: string; info: PollutantInfo }[] {
  return Object.entries(POLLUTANT_MAP)
    .filter(([_, info]) => info.category === category)
    .map(([code, info]) => ({ code, info }))
}

/**
 * 生成下拉选项列表
 */
export function generatePollutantOptions(codes?: string[]): { label: string; value: string }[] {
  const targetCodes = codes || Object.keys(POLLUTANT_MAP)
  const normalizedCodes = [...new Set(targetCodes.map(code => normalizePollutantCode(code)))]
  return normalizedCodes
    .filter(code => POLLUTANT_MAP[code])
    .map(code => ({
      label: `${POLLUTANT_MAP[code].name} (${code})`,
      value: code
    }))
}

/**
 * 生成分组的下拉选项（按类别分组）
 */
export function generateGroupedPollutantOptions() {
  const groups: { label: string; options: { label: string; value: string }[] }[] = []

  for (const [categoryKey, categoryInfo] of Object.entries(POLLUTANT_CATEGORIES)) {
    const pollutants = getPollutantsByCategory(categoryKey)
    if (pollutants.length > 0) {
      groups.push({
        label: categoryInfo.name,
        options: pollutants.map(p => ({
          label: `${p.info.name} (${p.code})`,
          value: p.code
        }))
      })
    }
  }

  return groups
}

/**
 * 判断是否为重金属
 */
export function isHeavyMetal(code: string): boolean {
  const normalizedCode = normalizePollutantCode(code)
  const category = POLLUTANT_MAP[normalizedCode]?.category
  return category === 'heavy_metals_class1' || category === 'heavy_metals_class2'
}

/**
 * 获取污染物的颜色（用于图表）
 * 使用现代柔和色系 - 中高饱和度，清晰可读且高级
 */
export function getPollutantColor(code: string, index: number = 0): string {
  const normalizedCode = normalizePollutantCode(code)

  // 现代柔和配色方案（中高饱和度，鲜活且高级）
  const colors: Record<string, string> = {
    // 常用指标
    'w01018': '#4A90C2', // COD - 清澈蓝
    'w21003': '#5AAF5A', // 氨氮 - 翠绿
    'w01001': '#E5A033', // pH - 琥珀金
    'w21011': '#D55A5A', // 总磷 - 珊瑚红
    'w21001': '#8B6B45', // 总氮 - 焦糖棕
    'w01020': '#45A8A8', // TOC - 孔雀青
    'w01010': '#E07878', // 水温 - 桃红
    'w00000': '#4A9DC2', // 流量 - 海洋蓝
    // 重金属 - 紫色调系列
    'w20111': '#8855BB', // 汞 - 鸢尾紫
    'w20115': '#9966CC', // 镉 - 薰衣草
    'w20117': '#6B5AAF', // 六价铬 - 靛蓝紫
    'w20119': '#C46666', // 砷 - 玫瑰红
    'w20120': '#8B8B55', // 铅 - 橄榄绿
    'w20121': '#559999', // 镍 - 湖水青
    'w20122': '#D4884A', // 铜 - 铜橙
    'w20123': '#7AAF55', // 锌 - 草绿
    // 其他物理指标
    'w01009': '#4A9DD4', // 溶解氧 - 晴空蓝
    'w01003': '#C9A033', // 浊度 - 金沙色
    'w01014': '#55A088', // 电导率 - 薄荷绿
    // 营养盐
    'w21006': '#55C299', // 亚硝酸盐氮 - 碧玉绿
    'w21007': '#66BB55', // 硝酸盐氮 - 嫩叶绿
    'w21023': '#C98855', // 磷酸盐 - 蜜糖色
  }

  if (colors[normalizedCode]) return colors[normalizedCode]

  // 默认现代柔和色系循环（16色）
  const modernSoftColors = [
    '#4A90C2', // 清澈蓝
    '#5AAF5A', // 翠绿
    '#E5A033', // 琥珀金
    '#D55A5A', // 珊瑚红
    '#8855BB', // 鸢尾紫
    '#45A8A8', // 孔雀青
    '#9966CC', // 薰衣草
    '#D4884A', // 铜橙
    '#4A9DC2', // 海洋蓝
    '#C46666', // 玫瑰红
    '#55C299', // 碧玉绿
    '#C9A033', // 金沙色
    '#559999', // 湖水青
    '#E07878', // 桃红
    '#8B6B45', // 焦糖棕
    '#7AAF55', // 草绿
  ]
  return modernSoftColors[index % modernSoftColors.length]
}
