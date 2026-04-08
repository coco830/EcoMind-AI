import type { IndustryType } from '@/api/devices'

export type DeviceType = 'water' | 'air' | 'noise' | 'soil'

const AIR_DEFAULT_LIMITS: Record<string, number> = {
  a21026: 100,
  a21002: 100,
  a34013: 30,
  a19001: 1,
}

const AIR_STANDARD_LIMITS: Record<string, Record<string, Record<string, number>>> = {
  // 火电厂大气污染物排放标准 (GB 13223-2011)
  'GB13223-2011': {
    default: {
      a21026: 100,
      a21002: 100,
      a34013: 30,
      a19001: 1,
    },
    special: {
      a21026: 50,
      a21002: 100,
      a34013: 20,
      a19001: 1,
    }
  },
  // 锅炉大气污染物排放标准 (GB 13271-2014) - default uses燃煤锅炉新建限值
  'GB13271-2014': {
    default: {
      a21026: 300,
      a21002: 300,
      a34013: 50,
      a19001: 1,
    },
    special: {
      a21026: 200,
      a21002: 200,
      a34013: 30,
      a19001: 1,
    }
  },
  // 陶瓷工业污染物排放标准 (GB 25464-2010)
  'GB25464-2010': {
    default: {
      a21026: 300,
      a21002: 450,
      a34013: 50,
      a19001: 1,
    }
  },
  // 铝工业污染物排放标准 (GB 25465-2010)
  'GB25465-2010': {
    default: {
      a21026: 400,
      a34013: 100,
    }
  },
  // 硫酸工业污染物排放标准 (GB 26132-2010)
  'GB26132-2010': {
    default: {
      a21026: 400,
      a34013: 50,
    },
    special: {
      a21026: 200,
      a34013: 30,
    }
  },
  // 硝酸工业污染物排放标准 (GB 26131-2010)
  'GB26131-2010': {
    default: {
      a21002: 300,
    },
    special: {
      a21002: 200,
    }
  },
  // 煤炭工业污染物排放标准 (GB 20426-2006)
  'GB20426-2006': {
    default: {
      a34013: 80,
    }
  },
  // 印刷工业大气污染物排放标准 (GB 41616-2022)
  'GB41616-2022': {
    default: {
      a21026: 200,
      a21002: 200,
      a34013: 30,
    }
  },
  // 电池工业污染物排放标准 (GB 30484-2013)
  'GB30484-2013': {
    default: {
      a21002: 50,
      a34013: 30,
    }
  },
  // 火葬场大气污染物排放标准 (GB 13801-2015)
  'GB13801-2015': {
    default: {
      a21026: 30,
      a21002: 200,
      a34013: 30,
      a19001: 1,
    }
  },
  'GB13810-2015': {
    default: {
      a21026: 30,
      a21002: 200,
      a34013: 30,
      a19001: 1,
    }
  },
  // 水泥工业大气污染物排放标准 (GB 4915-2013)
  'GB4915-2013': {
    default: {
      a21026: 200,
      a21002: 400,
      a34013: 30,
    }
  },
}

const GB16297_NEW_DEFAULT: Record<string, number> = {
  a21026: 550,
  a21002: 240,
  a34013: 120,
}

const GB16297_EXISTING_DEFAULT: Record<string, number> = {
  a21026: 1200,
  a21002: 700,
  a34013: 80,
}

const AIR_INDUSTRY_LIMITS: Record<string, Record<string, number>> = {
  thermal_power: {
    a21026: 100,
    a21002: 100,
    a34013: 30,
    a19001: 1,
  },
  cement: {
    a21026: 200,
    a21002: 400,
    a34013: 30,
  },
}

const AIR_AMBIENT_LIMITS: Record<string, number> = {
  a34004: 75,
  a34002: 150,
  a21004: 200,
  a05024: 200,
  a21026: 500,
}

const STANDARD_CODE_RE = /(GB|HJ)\s*\/?T?\s*\d{4,5}\s*[-—－]\s*\d{4}/i

function normalizeStandardCode(standard?: string | null): string | null {
  if (!standard) return null
  const match = standard.match(STANDARD_CODE_RE)
  if (!match) return null
  return match[0]
    .toUpperCase()
    .replace(/\s+/g, '')
    .replace(/[—－]/g, '-')
    .replace('GB/T', 'GB')
}

function isSpecialStandard(standard?: string | null): boolean {
  if (!standard) return false
  return ['特别', '重点', '超低', '严'].some(key => standard.includes(key))
}

function resolveGb16297Limit(pollutantCode: string, standard?: string | null): number | null {
  const text = standard ?? ''
  const isExisting = ['现有', '老'].some(key => text.includes(key))
  const base = isExisting ? GB16297_EXISTING_DEFAULT : GB16297_NEW_DEFAULT

  if (pollutantCode === 'a21026') {
    if (text.includes('生产')) return isExisting ? 1200 : 960
    if (text.includes('使用')) return isExisting ? 1200 : 550
    return base[pollutantCode] ?? null
  }
  if (pollutantCode === 'a21002') {
    if (text.includes('生产')) return isExisting ? 700 : 1400
    if (text.includes('使用')) return isExisting ? 700 : 240
    return base[pollutantCode] ?? null
  }
  if (pollutantCode === 'a34013') {
    if (['碳黑', '染料'].some(key => text.includes(key))) return isExisting ? 22 : 18
    if (['玻璃棉', '石英'].some(key => text.includes(key))) return isExisting ? 80 : 60
    if (['硝酸', '氮肥'].some(key => text.includes(key))) {
      if (isExisting) return text.includes('使用') ? 420 : 1700
      return base[pollutantCode] ?? null
    }
    if (text.includes('其他')) return base[pollutantCode] ?? null
    return base[pollutantCode] ?? null
  }

  return base[pollutantCode] ?? null
}

export function getStandardLimit(
  deviceType: DeviceType,
  pollutantCode: string,
  industryType?: IndustryType | null,
  nationalStandard?: string | null,
): number | null {
  if (!pollutantCode) return null
  const code = pollutantCode.toLowerCase()

  if (deviceType === 'air') {
    const standardCode = normalizeStandardCode(nationalStandard)
    if (standardCode === 'GB16297-1996') {
      const limit = resolveGb16297Limit(code, nationalStandard)
      if (limit !== null) return limit
    }
    if (standardCode && AIR_STANDARD_LIMITS[standardCode]?.default) {
      const variant = isSpecialStandard(nationalStandard) ? 'special' : 'default'
      const limit = AIR_STANDARD_LIMITS[standardCode]?.[variant]?.[code]
      if (limit !== undefined) return limit
    }
    if (industryType && AIR_INDUSTRY_LIMITS[industryType]?.[code] !== undefined) {
      return AIR_INDUSTRY_LIMITS[industryType][code]
    }
    if (AIR_AMBIENT_LIMITS[code] !== undefined) {
      return AIR_AMBIENT_LIMITS[code]
    }
    if (AIR_DEFAULT_LIMITS[code] !== undefined) {
      return AIR_DEFAULT_LIMITS[code]
    }
  }

  return null
}
