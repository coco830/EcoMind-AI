import { request, apiBasePath } from './request'
import axios from 'axios'

// ============== 类型定义 ==============

export type InspectionStatus = 'pending' | 'verified' | 'rejected'

export interface SelfInspectionDataItem {
  id?: string
  report_id?: string
  pollutant_code: string
  pollutant_name: string
  value: number
  unit: string
  standard_limit?: number | null
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

export interface AIReportResponse {
  report_id?: string | null
  period: string
  generated_at: string
  summary: string
  recommendations: string[]
  data_source_note: string
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
  page?: number
  page_size?: number
}

export interface TrendAnalysisRequest {
  start_date: string
  end_date: string
  pollutant_codes?: string[]
}

export interface AIReportRequest {
  start_date: string
  end_date: string
  report_type?: 'monthly' | 'quarterly'
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
   */
  async upload(
    file: File,
    inspectionDate?: string,
    inspectionAgency?: string,
    reportNumber?: string,
    useAiParsing: boolean = true
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

    // AI解析开关
    formData.append('use_ai_parsing', String(useAiParsing))

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
   */
  generateAIReport(data: AIReportRequest): Promise<AIReportResponse> {
    return request.post('/self-inspection/analysis/ai-report', data)
  }
}
