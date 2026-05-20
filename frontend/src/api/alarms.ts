import { request } from './request'

export interface Alarm {
  id: string
  device_id: string
  alarm_type: 'threshold' | 'anomaly' | 'offline' | 'flag'
  level: 'info' | 'warning' | 'critical'
  status: 'pending' | 'acknowledged' | 'resolved'
  pollutant_code: string | null
  message: string
  value: string | null
  threshold: string | null
  acknowledged_by: string | null
  acknowledged_at: string | null
  resolved_at: string | null
  created_at: string
  updated_at: string
}

export interface AlarmCreate {
  device_id: string
  alarm_type: 'threshold' | 'anomaly' | 'offline' | 'flag'
  level?: 'info' | 'warning' | 'critical'
  pollutant_code?: string
  message: string
  value?: string
  threshold?: string
}

export interface AlarmStats {
  total: number
  pending: number
  acknowledged: number
  resolved: number
  by_level: {
    info: number
    warning: number
    critical: number
  }
}

export const alarmApi = {
  list(params?: {
    device_id?: string
    status?: string
    level?: string
    start_time?: string
    end_time?: string
    skip?: number
    limit?: number
  }): Promise<Alarm[]> {
    return request.get('/alarms', { params })
  },

  getPending(limit?: number): Promise<Alarm[]> {
    return request.get('/alarms/pending', { params: { limit } })
  },

  get(id: string): Promise<Alarm> {
    return request.get(`/alarms/${id}`)
  },

  create(data: AlarmCreate): Promise<Alarm> {
    return request.post('/alarms', data)
  },

  acknowledge(id: string): Promise<Alarm> {
    return request.post(`/alarms/${id}/acknowledge`)
  },

  resolve(id: string): Promise<Alarm> {
    return request.post(`/alarms/${id}/resolve`)
  },

  delete(id: string): Promise<void> {
    return request.delete(`/alarms/${id}`)
  },

  getStats(): Promise<AlarmStats> {
    return request.get('/alarms/stats/summary')
  }
}
