import { request } from './request'

export type InvitationStatus = 'active' | 'used' | 'expired' | 'disabled'

export interface InvitationCode {
  id: string
  code: string
  name: string
  description: string | null
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
  expires_at?: string
}

export interface UpdateInvitationRequest {
  name?: string
  description?: string
  max_uses?: number
  expires_at?: string
  is_active?: boolean
}

export const invitationsApi = {
  // 获取所有邀请码（超级管理员）
  getAll(): Promise<InvitationCode[]> {
    return request.get('/invitations/')
  },

  // 获取单个邀请码
  getById(id: string): Promise<InvitationCode> {
    return request.get(`/invitations/${id}`)
  },

  // 创建邀请码
  create(data: CreateInvitationRequest): Promise<InvitationCode> {
    return request.post('/invitations/', data)
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
