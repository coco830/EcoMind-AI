import { request } from './request'

export type InvitationStatus = 'active' | 'used' | 'expired' | 'disabled'

export interface InvitationCode {
  id: string
  code: string
  name: string
  description: string | null
  org_type?: string | null
  region_code?: string | null
  region_name?: string | null
  park_code?: string | null
  park_name?: string | null
  industry_type?: string | null
  jurisdiction_level?: string | null
  jurisdiction_codes?: string[] | null
  org_id?: string | null
  org_name?: string | null
  max_uses: number
  used_count: number
  expires_at: string | null
  status: InvitationStatus
  is_active: boolean
  created_by: string | null
  created_at: string
  updated_at: string
}

export interface CreateInvitationRequest {
  name: string
  description?: string
  max_uses?: number
  expires_days?: number
  org_type?: string
  region_code?: string
  region_name?: string
  park_code?: string
  park_name?: string
  industry_type?: string
  jurisdiction_level?: string
  jurisdiction_codes?: string[]
}

export interface UpdateInvitationRequest {
  name?: string
  description?: string
  max_uses?: number
  is_active?: boolean
  region_code?: string
  region_name?: string
  park_code?: string
  park_name?: string
  industry_type?: string
  jurisdiction_level?: string
  jurisdiction_codes?: string[]
}

export const invitationsApi = {
  // 获取所有邀请码（超级管理员）
  getAll(): Promise<InvitationCode[]> {
    return request.get('/invitations')
  },

  // 获取单个邀请码
  getById(id: string): Promise<InvitationCode> {
    return request.get(`/invitations/${id}`)
  },

  // 创建邀请码
  create(data: CreateInvitationRequest): Promise<InvitationCode> {
    return request.post('/invitations', data)
  },

  // 更新邀请码
  update(id: string, data: UpdateInvitationRequest): Promise<InvitationCode> {
    return request.put(`/invitations/${id}`, data)
  },

  // 删除邀请码
  delete(id: string): Promise<void> {
    return request.delete(`/invitations/${id}`)
  }
}
