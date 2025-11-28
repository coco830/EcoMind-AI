import { request } from './request'
import type { MonitoringData } from './data'

export interface DashboardStats {
  device_count: number
  online_count: number
  offline_count: number
  alarm_count: number
  data_count: number
  pending_alarms: number
}

export interface TrendParams {
  device_id?: string
  pollutant_code?: string
  hours?: number
  limit?: number
}

export const dashboardApi = {
  /**
   * Get dashboard statistics (public endpoint)
   */
  getStats(): Promise<DashboardStats> {
    return request.get('/dashboard/stats')
  },

  /**
   * Get trend data for charts (public endpoint)
   */
  getTrend(params?: TrendParams): Promise<MonitoringData[]> {
    return request.get('/dashboard/trend', { params })
  },

  /**
   * Get latest monitoring data (public endpoint)
   */
  getLatest(limit?: number): Promise<MonitoringData[]> {
    return request.get('/dashboard/latest', { params: { limit } })
  },

  /**
   * Get real-time data (public endpoint)
   */
  getRealtime(limit?: number): Promise<MonitoringData[]> {
    return request.get('/dashboard/realtime', { params: { limit } })
  },

  /**
   * Get all pollutants data for a specific device (public endpoint)
   * Returns the latest value for each pollutant the device has reported
   */
  getDevicePollutants(deviceId: string, hours?: number): Promise<MonitoringData[]> {
    return request.get('/dashboard/device-pollutants', {
      params: { device_id: deviceId, hours: hours || 24 }
    })
  },

  /**
   * Inject demo data for testing (Mock mode only)
   */
  injectDemoData(params: {
    device_id?: string
    hours?: number
    interval_minutes?: number
    include_anomalies?: boolean
  }): Promise<{
    success: boolean
    message: string
    data_points: number
    pollutants: number
    anomalies: number
  }> {
    return request.post('/dashboard/demo/inject', null, { params })
  }
}
