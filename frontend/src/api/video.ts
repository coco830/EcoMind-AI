import { request } from './request'

export type VideoPointType =
  | 'station_room'
  | 'wastewater_outlet'
  | 'wastegas_outlet'
  | 'manual_sampling'
  | 'custom'

export type VideoProtocol = 'gb28181' | 'rtsp' | 'onvif' | 'http_link' | 'other'

export type VideoAccessMethod =
  | 'operator_platform'
  | 'city_platform'
  | 'direct'
  | 'external_link'

export type VideoLifecycleStatus =
  | 'pending_survey'
  | 'pending_installation'
  | 'pending_networking'
  | 'commissioning'
  | 'accepted'
  | 'active'

export type VideoChannelStatus = 'online' | 'offline' | 'fault' | 'unknown'

export type VideoEventType =
  | 'stream_offline'
  | 'occlusion'
  | 'intrusion'
  | 'loitering'
  | 'wastewater_visual_anomaly'
  | 'smoke_plume_change'
  | 'manual_sampling'
  | 'ai_linkage'
  | 'custom'

export type VideoEventSource = 'manual' | 'external_callback' | 'ai_linkage' | 'inspection'

export type VideoEventLevel = 'info' | 'warning' | 'critical'

export type VideoEventStatus = 'pending' | 'acknowledged' | 'resolved'

export interface VideoChannel {
  id: string
  org_id: string
  device_id: string
  device_mn: string
  device_name: string | null
  name: string
  point_type: VideoPointType
  protocol: VideoProtocol
  access_method: VideoAccessMethod
  lifecycle_status: VideoLifecycleStatus
  status: VideoChannelStatus
  vendor: string | null
  channel_code: string | null
  network_provider: string | null
  fixed_ip: string | null
  install_location: string | null
  surveyor_name: string | null
  installer_name: string | null
  accepted_by: string | null
  accepted_at: string | null
  acceptance_notes: string | null
  preview_url: string | null
  playback_url: string | null
  ai_enabled: boolean
  notes: string | null
  last_seen_at: string | null
  created_at: string
  updated_at: string | null
}

export interface VideoChannelCreate {
  device_id: string
  name: string
  point_type: VideoPointType
  protocol: VideoProtocol
  access_method: VideoAccessMethod
  lifecycle_status: VideoLifecycleStatus
  status: VideoChannelStatus
  vendor?: string
  channel_code?: string
  network_provider?: string
  fixed_ip?: string
  install_location?: string
  surveyor_name?: string
  installer_name?: string
  accepted_by?: string
  accepted_at?: string
  acceptance_notes?: string
  preview_url?: string
  playback_url?: string
  ai_enabled: boolean
  notes?: string
  last_seen_at?: string
}

export interface VideoEvent {
  id: string
  org_id: string
  channel_id: string
  channel_name: string | null
  device_id: string
  device_mn: string
  device_name: string | null
  related_alarm_id: string | null
  event_type: VideoEventType
  source: VideoEventSource
  level: VideoEventLevel
  status: VideoEventStatus
  title: string
  summary: string | null
  snapshot_uri: string | null
  clip_uri: string | null
  extra_data: Record<string, unknown> | null
  occurred_at: string
  created_at: string
  updated_at: string | null
}

export interface VideoEventCreate {
  channel_id: string
  related_alarm_id?: string
  event_type: VideoEventType
  source: VideoEventSource
  level: VideoEventLevel
  title: string
  summary?: string
  snapshot_uri?: string
  clip_uri?: string
  extra_data?: Record<string, unknown>
  occurred_at?: string
}

export interface VideoSummary {
  total_channels: number
  pending_survey_channels: number
  pending_installation_channels: number
  pending_networking_channels: number
  commissioning_channels: number
  accepted_channels: number
  online_channels: number
  ai_enabled_channels: number
  fault_channels: number
  today_events: number
  pending_events: number
  linked_alarm_events: number
}

export interface VideoDemoSeedRequest {
  org_id?: string
  device_id?: string
  replace_existing?: boolean
  create_demo_devices_if_missing?: boolean
}

export interface VideoDemoSeedResponse {
  success: boolean
  message: string
  org_id: string
  device_count: number
  created_devices: number
  created_channels: number
  created_events: number
  created_alarms: number
}

export const videoApi = {
  getSummary(params?: { org_id?: string }): Promise<VideoSummary> {
    return request.get('/video/summary', { params })
  },

  listChannels(params?: {
    org_id?: string
    device_id?: string
    point_type?: VideoPointType
    lifecycle_status?: VideoLifecycleStatus
    status?: VideoChannelStatus
    ai_enabled?: boolean
  }): Promise<VideoChannel[]> {
    return request.get('/video/channels', { params })
  },

  createChannel(data: VideoChannelCreate): Promise<VideoChannel> {
    return request.post('/video/channels', data)
  },

  injectDemoData(data: VideoDemoSeedRequest): Promise<VideoDemoSeedResponse> {
    return request.post('/video/demo/inject', data)
  },

  updateChannel(id: string, data: VideoChannelCreate): Promise<VideoChannel> {
    return request.put(`/video/channels/${id}`, data)
  },

  deleteChannel(id: string): Promise<{ message: string }> {
    return request.delete(`/video/channels/${id}`)
  },

  listEvents(params?: {
    org_id?: string
    device_id?: string
    channel_id?: string
    related_alarm_id?: string
    status?: VideoEventStatus
    level?: VideoEventLevel
    limit?: number
  }): Promise<VideoEvent[]> {
    return request.get('/video/events', { params })
  },

  createEvent(data: VideoEventCreate): Promise<VideoEvent> {
    return request.post('/video/events', data)
  },

  acknowledgeEvent(id: string): Promise<VideoEvent> {
    return request.post(`/video/events/${id}/acknowledge`)
  },

  resolveEvent(id: string): Promise<VideoEvent> {
    return request.post(`/video/events/${id}/resolve`)
  }
}
