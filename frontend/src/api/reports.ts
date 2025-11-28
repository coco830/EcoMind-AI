import { request } from './request'
import axios from 'axios'

export interface PollutantStats {
  pollutant_code: string
  pollutant_name: string
  unit: string
  min_value: number
  max_value: number
  avg_value: number
  std_value: number
  data_count: number
  exceedance_count: number
  threshold: number | null
  abnormal_flag_count: number
}

export interface ReportSummary {
  total_records: number
  expected_records: number
  capture_rate: number
  exceedance_count: number
}

export interface ReportPeriod {
  start: string
  end: string
  days: number
}

export interface ReportPreview {
  device_id: string
  device_name: string
  period: ReportPeriod
  pollutants: PollutantStats[]
  summary: ReportSummary
}

export interface ReportRequest {
  device_id: string
  report_type: 'daily' | 'monthly'
  report_date?: string  // YYYY-MM-DD for daily report
  year?: number         // for monthly report
  month?: number        // 1-12 for monthly report
}

export interface ReportDevice {
  id: string
  mn: string
  name: string
  device_type: string
  pollutant_codes: string[]
}

export const reportApi = {
  /**
   * Preview report statistics
   */
  preview(data: ReportRequest): Promise<ReportPreview> {
    return request.post('/reports/preview', data)
  },

  /**
   * Download report file (Excel or PDF)
   */
  async download(data: ReportRequest, format: 'excel' | 'pdf' = 'excel'): Promise<void> {
    const token = localStorage.getItem('token')

    const response = await axios.post(
      `/api/v1/reports/download?format=${format}`,
      data,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        responseType: 'blob'
      }
    )

    // Extract filename from Content-Disposition header
    const contentDisposition = response.headers['content-disposition']
    let filename = `report.${format === 'excel' ? 'xlsx' : 'pdf'}`

    if (contentDisposition) {
      // Handle UTF-8 encoded filename (RFC 5987)
      const utf8Match = contentDisposition.match(/filename\*=UTF-8''(.+)/)
      if (utf8Match) {
        filename = decodeURIComponent(utf8Match[1])
      } else {
        // Try standard filename
        const standardMatch = contentDisposition.match(/filename="?(.+)"?/)
        if (standardMatch) {
          filename = standardMatch[1].replace(/"/g, '')
        }
      }
    }

    // Create download link
    const blob = new Blob([response.data], {
      type: format === 'excel'
        ? 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        : 'application/pdf'
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

  /**
   * List devices available for report generation
   */
  listDevices(): Promise<ReportDevice[]> {
    return request.get('/reports/devices')
  }
}
