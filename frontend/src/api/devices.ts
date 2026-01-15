import { request } from './request'

export interface PollutantThreshold {
  pollutant_code: string
  pollutant_name: string
  warning_value: number
  alarm_value: number
  unit: string
}

export interface ThresholdConfig {
  enabled: boolean
  pollutants: PollutantThreshold[]
}

export interface PollutantTemplate {
  code: string
  name: string
  unit: string
  defaultWarning: number
  defaultAlarm: number
}

// 行业类型枚举
export type IndustryType =
  | 'municipal_wastewater'  // 城镇污水处理厂
  | 'electroplating'        // 电镀工业
  | 'textile_dyeing'        // 纺织染整工业
  | 'thermal_power'         // 火电厂
  | 'pharmaceutical'        // 制药工业
  | 'paper_making'          // 造纸工业
  | 'petrochemical'         // 石油化工
  | 'steel'                 // 钢铁工业
  | 'cement'                // 水泥工业
  | 'other'                 // 其他

// 行业类型信息接口
export interface IndustryTypeInfo {
  code: IndustryType
  name: string
  standard: string
  standard_name: string
}

export interface Device {
  id: string
  mn: string
  name: string
  device_type: 'water' | 'air' | 'noise' | 'soil'
  status: 'online' | 'offline' | 'alarm' | 'maintenance'
  org_id: string
  industry_type: IndustryType | null
  national_standard: string | null
  latitude: number | null
  longitude: number | null
  address: string | null
  pollutant_codes: string[] | null
  thresholds: ThresholdConfig | null
  last_heartbeat: string | null
  created_at: string
  updated_at: string
}

export interface DeviceCreate {
  mn: string
  name: string
  device_type: 'water' | 'air' | 'noise' | 'soil'
  org_id?: string  // 可选，不传则使用当前用户的组织
  industry_type?: IndustryType  // 行业类型
  national_standard?: string    // 执行标准号
  latitude?: number
  longitude?: number
  address?: string
  pollutant_codes?: string[]
  thresholds?: ThresholdConfig
}

// Predefined pollutant options for different device types
export const POLLUTANT_OPTIONS = {
  water: [
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 35, defaultAlarm: 40 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 12, defaultAlarm: 15 },
    { code: 'w01001', name: 'pH值', unit: '', defaultWarning: 8.5, defaultAlarm: 9.0 },
    { code: 'w01010', name: '总磷', unit: 'mg/L', defaultWarning: 0.8, defaultAlarm: 1.0 },
    { code: 'w21011', name: '总氮', unit: 'mg/L', defaultWarning: 12, defaultAlarm: 15 },
  ],
  air: [
    { code: 'a34004', name: 'PM2.5', unit: 'ug/m³', defaultWarning: 55, defaultAlarm: 75 },
    { code: 'a34002', name: 'PM10', unit: 'ug/m³', defaultWarning: 120, defaultAlarm: 150 },
    { code: 'a21004', name: 'NO2', unit: 'ug/m³', defaultWarning: 160, defaultAlarm: 200 },
    { code: 'a21026', name: 'SO2', unit: 'ug/m³', defaultWarning: 400, defaultAlarm: 500 },
    { code: 'a05024', name: 'O3', unit: 'ug/m³', defaultWarning: 160, defaultAlarm: 200 },
  ],
  noise: [
    { code: 'e01001', name: '噪声', unit: 'dB(A)', defaultWarning: 55, defaultAlarm: 65 },
  ],
  soil: [
    { code: 's01001', name: 'pH值', unit: '', defaultWarning: 8.5, defaultAlarm: 9.5 },
    { code: 's01002', name: '重金属含量', unit: 'mg/kg', defaultWarning: 100, defaultAlarm: 150 },
  ],
}

// 更丰富的废水行业模板（默认优先用 industry_type 匹配，没有则使用 default）
export const WATER_TEMPLATES: Record<'default' | IndustryType, PollutantTemplate[]> = {
  default: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 50, defaultAlarm: 60 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6.5, defaultAlarm: 9.0 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 40, defaultAlarm: 50 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 15, defaultAlarm: 20 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 7, defaultAlarm: 10 },
    { code: 'w21011', name: '总氮', unit: 'mg/L', defaultWarning: 15, defaultAlarm: 20 },
    { code: 'w01010', name: '总磷', unit: 'mg/L', defaultWarning: 0.8, defaultAlarm: 1.0 },
    { code: 'w01009', name: '溶解氧', unit: 'mg/L', defaultWarning: 2, defaultAlarm: 1 },
    { code: 'w01014', name: '电导率', unit: 'µS/cm', defaultWarning: 1500, defaultAlarm: 2000 },
    { code: 'w01003', name: '浊度', unit: 'NTU', defaultWarning: 10, defaultAlarm: 20 }
  ],
  municipal_wastewater: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 50, defaultAlarm: 70 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6.5, defaultAlarm: 9.0 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 45, defaultAlarm: 50 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 18, defaultAlarm: 20 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 6, defaultAlarm: 8 },
    { code: 'w21011', name: '总氮', unit: 'mg/L', defaultWarning: 15, defaultAlarm: 20 },
    { code: 'w01010', name: '总磷', unit: 'mg/L', defaultWarning: 0.8, defaultAlarm: 1.0 },
    { code: 'w01009', name: '溶解氧', unit: 'mg/L', defaultWarning: 2, defaultAlarm: 1 },
    { code: 'w01014', name: '电导率', unit: 'µS/cm', defaultWarning: 1500, defaultAlarm: 2000 },
    { code: 'w01003', name: '浊度', unit: 'NTU', defaultWarning: 10, defaultAlarm: 20 }
  ],
  electroplating: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 20, defaultAlarm: 30 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 20, defaultAlarm: 30 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 8, defaultAlarm: 12 },
    { code: 'w21011', name: '总氮', unit: 'mg/L', defaultWarning: 20, defaultAlarm: 30 },
    { code: 'w01010', name: '总磷', unit: 'mg/L', defaultWarning: 1.0, defaultAlarm: 1.5 },
    { code: 'w20117', name: '总铬', unit: 'mg/L', defaultWarning: 0.2, defaultAlarm: 0.5 },
    { code: 'w20123', name: '六价铬', unit: 'mg/L', defaultWarning: 0.05, defaultAlarm: 0.1 }
  ],
  textile_dyeing: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 40, defaultAlarm: 60 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 25, defaultAlarm: 30 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 8, defaultAlarm: 12 },
    { code: 'w20117', name: '总铬', unit: 'mg/L', defaultWarning: 0.2, defaultAlarm: 0.5 }
  ],
  thermal_power: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6.5, defaultAlarm: 9.0 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 40, defaultAlarm: 50 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 8, defaultAlarm: 12 },
    { code: 'w21011', name: '总氮', unit: 'mg/L', defaultWarning: 15, defaultAlarm: 20 },
    { code: 'w01010', name: '总磷', unit: 'mg/L', defaultWarning: 0.8, defaultAlarm: 1.0 }
  ],
  pharmaceutical: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 30, defaultAlarm: 40 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 25, defaultAlarm: 30 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 8, defaultAlarm: 12 },
    { code: 'w21011', name: '总氮', unit: 'mg/L', defaultWarning: 20, defaultAlarm: 30 }
  ],
  paper_making: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 60, defaultAlarm: 80 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 90, defaultAlarm: 110 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 30, defaultAlarm: 40 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 10, defaultAlarm: 15 },
    { code: 'w20117', name: '总铬', unit: 'mg/L', defaultWarning: 0.2, defaultAlarm: 0.5 }
  ],
  petrochemical: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 60, defaultAlarm: 80 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 25, defaultAlarm: 35 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 8, defaultAlarm: 12 },
    { code: 'w20117', name: '总铬', unit: 'mg/L', defaultWarning: 0.2, defaultAlarm: 0.5 },
    { code: 'w21016', name: '总氰化物', unit: 'mg/L', defaultWarning: 0.1, defaultAlarm: 0.2 }
  ],
  steel: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 10, defaultAlarm: 15 },
    { code: 'w20117', name: '总铬', unit: 'mg/L', defaultWarning: 0.2, defaultAlarm: 0.5 }
  ],
  cement: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 40, defaultAlarm: 60 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 80, defaultAlarm: 100 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 10, defaultAlarm: 15 }
  ],
  other: [
    { code: 'w00001', name: '流量', unit: 'm³/h', defaultWarning: 40, defaultAlarm: 60 },
    { code: 'w01001', name: 'pH', unit: '', defaultWarning: 6, defaultAlarm: 9 },
    { code: 'w01018', name: 'COD', unit: 'mg/L', defaultWarning: 60, defaultAlarm: 80 },
    { code: 'w01002', name: 'BOD₅', unit: 'mg/L', defaultWarning: 20, defaultAlarm: 30 },
    { code: 'w21003', name: '氨氮', unit: 'mg/L', defaultWarning: 8, defaultAlarm: 12 }
  ]
}

export const getWaterThresholdTemplate = (industryType?: IndustryType): ThresholdConfig => {
  const list = (industryType && WATER_TEMPLATES[industryType]) || WATER_TEMPLATES.default
  return {
    enabled: true,
    pollutants: list.map(item => ({
      pollutant_code: item.code,
      pollutant_name: item.name,
      unit: item.unit,
      warning_value: item.defaultWarning,
      alarm_value: item.defaultAlarm,
    })),
  }
}

export interface DeviceStats {
  total: number
  online: number
  offline: number
  alarm: number
  maintenance: number
}

export const deviceApi = {
  list(params?: {
    org_id?: string
    status?: string
    skip?: number
    limit?: number
  }): Promise<Device[]> {
    return request.get('/devices', { params })
  },

  get(id: string): Promise<Device> {
    return request.get(`/devices/${id}`)
  },

  create(data: DeviceCreate): Promise<Device> {
    return request.post('/devices', data)
  },

  update(id: string, data: DeviceCreate): Promise<Device> {
    return request.put(`/devices/${id}`, data)
  },

  delete(id: string): Promise<void> {
    return request.delete(`/devices/${id}`)
  },

  getStats(): Promise<DeviceStats> {
    return request.get('/devices/stats/summary')
  },

  getIndustryTypes(): Promise<IndustryTypeInfo[]> {
    return request.get('/devices/industry-types')
  }
}
