import { request } from './request'

export interface MonitoringData {
  ts: string
  device_id: string
  pollutant_code: string
  value: number
  flag: string
  status: number
}

export interface DataQueryParams {
  device_id?: string
  pollutant_code?: string
  start_time?: string
  end_time?: string
  limit?: number
}

export interface DataStats {
  device_id: string
  pollutant_code: string
  min_value: number
  max_value: number
  avg_value: number
  count: number
  start_time: string
  end_time: string
}

export const dataApi = {
  query(params: DataQueryParams): Promise<MonitoringData[]> {
    return request.get('/data', { params })
  },

  getLatest(params?: { device_id?: string; limit?: number }): Promise<MonitoringData[]> {
    return request.get('/data/latest', { params })
  },

  getRealtime(deviceId: string): Promise<MonitoringData[]> {
    return request.get(`/data/realtime/${deviceId}`)
  },

  getHistory(
    deviceId: string,
    params?: {
      pollutant_code?: string
      start_time?: string
      end_time?: string
      limit?: number
    }
  ): Promise<MonitoringData[]> {
    return request.get(`/data/history/${deviceId}`, { params })
  },

  getStats(
    deviceId: string,
    params?: {
      pollutant_code?: string
      start_time?: string
      end_time?: string
    }
  ): Promise<DataStats[]> {
    return request.get(`/data/stats/${deviceId}`, { params })
  },

  export(params: {
    device_id: string
    pollutant_code?: string
    start_time?: string
    end_time?: string
    format?: 'json' | 'csv'
  }): Promise<{ data: unknown; format: string }> {
    return request.get('/data/export', { params })
  }
}
