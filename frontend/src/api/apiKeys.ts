import { request } from './request'

export type ApiKeyAccessScope = 'single_org' | 'all_orgs'

export interface ApiKeyItem {
  id: string
  api_key: string
  name: string
  org_id: string
  access_scope: ApiKeyAccessScope
  permissions: string | null
  rate_limit: number
  is_active: boolean
  expires_at: string | null
  created_at: string
  updated_at: string
}

export interface CreateApiKeyRequest {
  name: string
  org_id: string
  access_scope?: ApiKeyAccessScope
  permissions?: string[]
  rate_limit?: number
  expires_at?: string
}

export const apiKeysApi = {
  create(data: CreateApiKeyRequest): Promise<ApiKeyItem> {
    return request.post('/api-keys', data)
  },

  list(params?: {
    org_id?: string
    access_scope?: ApiKeyAccessScope
    skip?: number
    limit?: number
  }): Promise<ApiKeyItem[]> {
    return request.get('/api-keys', { params })
  },

  revoke(clientId: string): Promise<{ success: boolean; message: string }> {
    return request.delete(`/api-keys/${clientId}`)
  },

  toggle(clientId: string): Promise<ApiKeyItem> {
    return request.patch(`/api-keys/${clientId}/toggle`)
  }
}
