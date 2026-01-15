import { request } from './request'

export interface Organization {
  id: string
  name: string
  code: string
  address: string | null
  contact_name: string | null
  contact_phone: string | null
  created_at: string
  updated_at: string
}

export interface OrganizationWithStats extends Organization {
  user_count: number
  device_count: number
}

export const organizationApi = {
  // 获取组织列表（超管/平台员工可用；销售角色后端会做脱敏）
  list(params?: { skip?: number; limit?: number }): Promise<Organization[]> {
    return request.get('/organizations', { params })
  },

  // 获取单个组织详情（含统计）
  get(id: string): Promise<OrganizationWithStats> {
    return request.get(`/organizations/${id}`)
  }
}
