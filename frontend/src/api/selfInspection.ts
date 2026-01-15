import { request, apiBasePath } from './request'
import axios from 'axios'

// ============== 类型定义 ==============

export type InspectionStatus = 'pending' | 'verified' | 'rejected'

export interface SelfInspectionDataItem {
  id?: string
  report_id?: string
  pollutant_code: string
  pollutant_name: string
  value: number | string  // Support scientific notation like "4.0×10²"
  unit: string
  standard_limit?: number | string | null  // Support scientific notation
  is_compliant: boolean
  sampling_point?: string | null
  sampling_time?: string | null
  remarks?: string | null
  created_at?: string
}

export interface SelfInspectionReport {
  id: string
  org_id: string
  inspection_date: string
  inspection_agency: string
  report_number?: string | null
  original_file_name?: string | null
  ocr_confidence?: number | null
  status: InspectionStatus
  is_verified: boolean
  verified_at?: string | null
  remarks?: string | null
  created_at: string
  updated_at: string
  data_items: SelfInspectionDataItem[]
}

export interface SelfInspectionReportListItem {
  id: string
  org_id: string
  inspection_date: string
  inspection_agency: string
  report_number?: string | null
  original_file_name?: string | null
  status: InspectionStatus
  is_verified: boolean
  data_count: number
  created_at: string
}

export interface PaginatedReportList {
  items: SelfInspectionReportListItem[]
  total: number
  page: number
  page_size: number
}

export interface OCRUploadResponse {
  report_id: string
  ocr_confidence?: number | null
  recognized_data: SelfInspectionDataItem[]
  raw_text?: string | null
  message: string
}

export interface TrendDataPoint {
  date: string
  pollutant_code: string
  pollutant_name: string
  value: number
  unit: string
  standard_limit?: number | null
  is_compliant: boolean
}

export interface TrendStatistics {
  [pollutant_code: string]: {
    count: number
    min: number
    max: number
    avg: number
    name: string
  }
}

export interface TrendAnalysisResponse {
  start_date: string
  end_date: string
  data_points: TrendDataPoint[]
  statistics: TrendStatistics
}

export interface PollutantLoadItem {
  name: string
  avg_concentration_mg_l: number
  daily_volume_m3: number
  daily_load_kg: number
  monthly_load_kg: number
  formula: string
}

export interface PollutantLoads {
  flow_source: string
  concentration_source: string
  avg_flow_l_s: number
  daily_volume_m3: number
  pollutant_loads: { [code: string]: PollutantLoadItem }
  note: string
}

export interface AIReportResponse {
  report_id?: string | null
  period: string
  generated_at: string
  summary: string
  recommendations: string[]
  data_source_note: string
  flow_data?: {
    avg_flow: number
    max_flow: number
    min_flow: number
    total_volume: number
    daily_volume_m3?: number
    period_total_volume_m3?: number
    data_points_count: number
    device_count?: number
    devices?: Array<{
      device_mn: string
      device_name: string
      avg_flow: number
      max_flow: number
      min_flow: number
      data_points_count: number
    }>
  } | null
  online_data?: {
    start_time: string
    end_time: string
    pollutants: Array<{
      pollutant_code: string
      pollutant_name: string
      unit?: string | null
      min: number | null
      max: number | null
      avg: number | null
      count: number
      device_count: number
    }>
    note?: string
  } | null
  pollutant_loads?: PollutantLoads | null
}

// ============== 设备流量类型（数采仪只读数据） ==============

export interface FlowTrendPoint {
  ts: string
  value: number
  flag: string
}

export interface DeviceFlowData {
  device_id: string
  device_name: string
  device_status: 'online' | 'offline' | 'alarm' | 'unknown'
  latest_flow: number | null
  latest_flow_ts: string | null
  flow_unit: string
  data_source: string
  trend_data?: FlowTrendPoint[] | null
}

export interface DeviceFlowListResponse {
  devices: DeviceFlowData[]
  org_name: string
  query_time: string
  data_source_note: string
}

export interface FlowStatistics {
  avg_flow: number
  max_flow: number
  min_flow: number
  total_volume: number
  unit: string
  data_points_count: number
}

// ============== 请求参数类型 ==============

export interface CreateReportRequest {
  inspection_date: string
  inspection_agency: string
  report_number?: string
  remarks?: string
  data_items: Omit<SelfInspectionDataItem, 'id' | 'report_id' | 'created_at'>[]
}

export interface UpdateReportRequest {
  inspection_date?: string
  inspection_agency?: string
  report_number?: string
  status?: InspectionStatus
  remarks?: string
  data_items?: Omit<SelfInspectionDataItem, 'id' | 'report_id' | 'created_at'>[]
}

export interface ListReportsParams {
  start_date?: string
  end_date?: string
  status?: InspectionStatus
  target_org_id?: string  // 超级管理员按企业过滤
  page?: number
  page_size?: number
}

export interface TrendAnalysisRequest {
  start_date: string
  end_date: string
  pollutant_codes?: string[]
  target_org_id?: string  // 超级管理员按企业过滤
}

export interface AIReportRequest {
  start_date: string
  end_date: string
  report_type?: 'monthly' | 'quarterly'
  include_flow_data?: boolean
  calculate_pollutant_load?: boolean
  target_org_id?: string  // 超级管理员指定目标组织
}

export interface DeviceFlowParams {
  hours?: number
  include_history?: boolean
  target_org_id?: string  // 超级管理员指定目标组织
}

export interface FlowStatisticsParams {
  device_id: string
  start_date: string
  end_date: string
}

// ============== API 方法 ==============

export const selfInspectionApi = {
  /**
   * 上传检测报告并进行OCR+AI智能解析
   * @param file 检测报告文件
   * @param inspectionDate 检测日期（可选，AI会自动识别）
   * @param inspectionAgency 检测机构（可选，AI会自动识别）
   * @param reportNumber 报告编号（可选）
   * @param useAiParsing 是否使用AI智能解析（默认true）
   * @param targetOrgId 目标组织ID（超级管理员专用）
   */
  async upload(
    file: File,
    inspectionDate?: string,
    inspectionAgency?: string,
    reportNumber?: string,
    useAiParsing: boolean = true,
    targetOrgId?: string
  ): Promise<OCRUploadResponse> {
    const formData = new FormData()
    formData.append('file', file)

    // 可选参数：如果提供则添加到formData
    if (inspectionDate) {
      formData.append('inspection_date', inspectionDate)
    }
    if (inspectionAgency) {
      formData.append('inspection_agency', inspectionAgency)
    }
    if (reportNumber) {
      formData.append('report_number', reportNumber)
    }
    // 目标组织ID（超级管理员为企业上传报告时使用）
    if (targetOrgId) {
      formData.append('target_org_id', targetOrgId)
    }

    // AI解析开关 - FastAPI Form 接收布尔值需要用 'true'/'false' 字符串
    formData.append('use_ai_parsing', useAiParsing ? 'true' : 'false')

    const token = localStorage.getItem('token')
    const response = await axios.post<OCRUploadResponse>(
      `${apiBasePath}/self-inspection/upload`,
      formData,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        },
        timeout: 120000  // 增加超时时间到2分钟，因为AI解析可能需要更长时间
      }
    )
    return response.data
  },

  /**
   * 手动创建自检报告
   */
  create(data: CreateReportRequest): Promise<SelfInspectionReport> {
    return request.post('/self-inspection', data)
  },

  /**
   * 获取报告列表
   */
  list(params?: ListReportsParams): Promise<PaginatedReportList> {
    return request.get('/self-inspection', { params })
  },

  /**
   * 获取单个报告详情
   */
  get(reportId: string): Promise<SelfInspectionReport> {
    return request.get(`/self-inspection/${reportId}`)
  },

  /**
   * 更新报告（校验/修正数据）
   */
  update(reportId: string, data: UpdateReportRequest): Promise<SelfInspectionReport> {
    return request.put(`/self-inspection/${reportId}`, data)
  },

  /**
   * 删除报告
   */
  delete(reportId: string): Promise<{ message: string }> {
    return request.delete(`/self-inspection/${reportId}`)
  },

  /**
   * 校验报告（快捷方法）
   */
  verify(reportId: string, dataItems?: Omit<SelfInspectionDataItem, 'id' | 'report_id' | 'created_at'>[]): Promise<SelfInspectionReport> {
    const data: UpdateReportRequest = {
      status: 'verified'
    }
    if (dataItems) {
      data.data_items = dataItems
    }
    return request.put(`/self-inspection/${reportId}`, data)
  },

  /**
   * 获取趋势分析数据
   */
  getTrendAnalysis(data: TrendAnalysisRequest): Promise<TrendAnalysisResponse> {
    return request.post('/self-inspection/analysis/trend', data)
  },

  /**
   * 生成AI运维报告
   * @param data 报告请求参数，支持可选的流量数据整合
   */
  generateAIReport(data: AIReportRequest): Promise<AIReportResponse> {
    return request.post('/self-inspection/analysis/ai-report', data)
  },

  // ============== 设备流量 API（数采仪只读数据） ==============

  /**
   * 获取企业设备瞬时流量数据（只读）
   * 数据来自数采仪，不存储到自检报告
   * @param params.hours 查询最近多少小时的数据（默认24）
   * @param params.include_history 是否包含趋势数据点
   */
  getDeviceFlow(params?: DeviceFlowParams): Promise<DeviceFlowListResponse> {
    return request.get('/self-inspection/device-flow', { params })
  },

  /**
   * 获取设备流量统计数据（只读）
   * 用于AI报告的污染负荷计算
   */
  getFlowStatistics(params: FlowStatisticsParams): Promise<FlowStatistics> {
    return request.get('/self-inspection/device-flow/statistics', { params })
  }
  ,

  // ============== 在线监测数据（设备 -> 指标） ==============

  /**
   * 获取企业在线监测可用指标列表（来自实际数据出现情况）
   */
  getOnlineMetricOptions(params?: { hours?: number; target_org_id?: string }): Promise<Array<{ pollutant_code: string; pollutant_name: string; unit?: string | null }>> {
    return request.get('/self-inspection/online-metrics/options', { params })
  },

  /**
   * 获取企业设备在线监测数据（按指定指标）
   */
  getDeviceOnlineMetrics(params: { pollutant_code: string; hours?: number; include_history?: boolean; target_org_id?: string }): Promise<{
    pollutant_code: string
    pollutant_name: string
    unit?: string | null
    devices: Array<{
      device_id: string
      device_name: string
      device_status: 'online' | 'offline' | 'alarm' | 'unknown'
      pollutant_code: string
      pollutant_name: string
      unit?: string | null
      latest_value: number | null
      latest_ts: string | null
      data_source: string
      trend_data?: Array<{ ts: string; value: number; flag: string }> | null
    }>
    org_name: string
    query_time: string
    data_source_note: string
  }> {
    return request.get('/self-inspection/online-metrics', { params })
  }
}
