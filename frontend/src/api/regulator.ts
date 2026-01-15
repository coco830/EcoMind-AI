import { request, apiBasePath } from './request'
import axios from 'axios'

export interface RegulatorRiskDistribution {
  level: string
  count: number
}

export interface RegulatorIndustryDistribution {
  industry: string
  count: number
  insufficient: boolean
}

export interface RegulatorRegionDistribution {
  region_code: string
  count: number
}

export interface RegulatorOverview {
  target_date?: string
  start_date?: string
  end_date?: string
  enterprise_count: number
  device_count: number
  online_device_count: number
  offline_device_count: number
  risk_distribution: RegulatorRiskDistribution[]
  industry_distribution: RegulatorIndustryDistribution[]
  region_distribution: RegulatorRegionDistribution[]
}

export interface RegulatorHeatmapCell {
  h3_index: string
  boundary: number[][]
  risk_level: string
  risk_score: number
  enterprise_count: number
  device_count: number
}

export interface RegulatorHeatmap {
  target_date: string
  resolution: number
  cells: RegulatorHeatmapCell[]
}

export interface RegulatorTrendItem {
  date: string
  risk_distribution: RegulatorRiskDistribution[]
}

export interface RegulatorTrends {
  granularity: 'daily' | 'monthly'
  series: RegulatorTrendItem[]
}

export interface RegulatorConsistencySummary {
  high: number
  medium: number
  low: number
}

export interface RegulatorConsistencyItem {
  industry?: string
  region_code?: string
  high: number
  medium: number
  low: number
}

export interface RegulatorConsistency {
  summary: RegulatorConsistencySummary
  industry_breakdown: RegulatorConsistencyItem[]
  region_breakdown: RegulatorConsistencyItem[]
}

export interface RegulatorOverviewParams {
  target_date?: string
  region_code?: string
  park_code?: string
}

export interface RegulatorHeatmapParams extends RegulatorOverviewParams {
  resolution?: number
}

export interface RegulatorTrendsParams {
  start_date?: string
  end_date?: string
  granularity?: 'daily' | 'monthly'
}

export interface RegulatorReportParams {
  report_type: 'daily' | 'monthly'
  target_date?: string
  year?: number
  month?: number
  format?: 'excel' | 'pdf'
  region_code?: string
  park_code?: string
}

export interface RegulatorBriefOverview {
  enterprise_count: number
  device_count: number
  online_rate: number
  offline_rate: number
  alarm_rate: number
  exceed_rate: number
  invalid_rate: number
  risk_level: string
  risk_score: number
  risk_trend: string
}

export interface RegulatorBriefRankItem {
  code: string
  name: string
  risk_score: number
  risk_level: string
  enterprise_count: number
  share: number
  insufficient?: boolean
}

export interface RegulatorBriefQuota {
  limit: number
  remaining: number
}

export interface RegulatorBrief {
  period: 'daily' | 'monthly'
  period_label: string
  start_date: string
  end_date: string
  scope: { region_code?: string | null; park_code?: string | null }
  summary_text: string
  highlights: string[]
  suggestions: string[]
  quota: RegulatorBriefQuota
  overview: RegulatorBriefOverview
  top_regions: RegulatorBriefRankItem[]
  top_industries: RegulatorBriefRankItem[]
  industry_distribution: RegulatorIndustryDistribution[]
  consistency: RegulatorConsistency
  data_note: string
}

export interface RegulatorBriefParams {
  period?: 'daily' | 'monthly'
  target_date?: string
  year?: number
  month?: number
  region_code?: string
  park_code?: string
}

export interface RegulatorBriefDownloadParams extends RegulatorBriefParams {
  format?: 'excel' | 'pdf'
}

export const regulatorApi = {
  getOverview(params?: RegulatorOverviewParams): Promise<RegulatorOverview> {
    return request.get('/regulator/overview', { params })
  },

  getHeatmap(params?: RegulatorHeatmapParams): Promise<RegulatorHeatmap> {
    return request.get('/regulator/heatmap', { params })
  },

  getTrends(params?: RegulatorTrendsParams): Promise<RegulatorTrends> {
    return request.get('/regulator/trends', { params })
  },

  getConsistency(params?: { start_date?: string; end_date?: string }): Promise<RegulatorConsistency> {
    return request.get('/regulator/consistency', { params })
  },

  async downloadReport(params: RegulatorReportParams): Promise<void> {
    const token = localStorage.getItem('token')

    const query: Record<string, string | number> = {
      report_type: params.report_type,
      format: params.format || 'excel'
    }

    if (params.target_date) query.target_date = params.target_date
    if (params.year) query.year = params.year
    if (params.month) query.month = params.month
    if (params.region_code) query.region_code = params.region_code
    if (params.park_code) query.park_code = params.park_code

    const response = await axios.get(`${apiBasePath}/regulator/reports/download`, {
      params: query,
      headers: {
        Authorization: `Bearer ${token}`
      },
      responseType: 'blob'
    })

    const contentDisposition = response.headers['content-disposition']
    let filename = `regulator_report.${params.format === 'pdf' ? 'pdf' : 'xlsx'}`

    if (contentDisposition) {
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''(.+)/)
      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1])
      } else {
        const standardMatch = contentDisposition.match(/filename="?(.+)"?/)
        if (standardMatch) {
          filename = standardMatch[1].replace(/"/g, '')
        }
      }
    }

    const blob = new Blob([response.data], {
      type: params.format === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  },

  getBrief(params?: RegulatorBriefParams): Promise<RegulatorBrief> {
    return request.get('/regulator/brief', { params })
  },

  async downloadBrief(params: RegulatorBriefDownloadParams): Promise<void> {
    const token = localStorage.getItem('token')
    const query: Record<string, string | number> = {
      period: params.period || 'daily',
      format: params.format || 'excel'
    }

    if (params.target_date) query.target_date = params.target_date
    if (params.year) query.year = params.year
    if (params.month) query.month = params.month
    if (params.region_code) query.region_code = params.region_code
    if (params.park_code) query.park_code = params.park_code

    const response = await axios.get(`${apiBasePath}/regulator/brief/download`, {
      params: query,
      headers: {
        Authorization: `Bearer ${token}`
      },
      responseType: 'blob'
    })

    const contentDisposition = response.headers['content-disposition']
    let filename = `regulator_brief.${params.format === 'pdf' ? 'pdf' : 'xlsx'}`

    if (contentDisposition) {
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''(.+)/)
      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1])
      } else {
        const standardMatch = contentDisposition.match(/filename="?(.+)"?/)
        if (standardMatch) {
          filename = standardMatch[1].replace(/"/g, '')
        }
      }
    }

    const blob = new Blob([response.data], {
      type: params.format === 'pdf'
        ? 'application/pdf'
        : 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
  }
}
