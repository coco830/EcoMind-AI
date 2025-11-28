import { request } from './request'

export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  role: 'admin' | 'operator' | 'viewer'
  is_active: boolean
  org_id: string | null
  created_at: string
  updated_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface RegisterRequest {
  username: string
  email: string
  password: string
  full_name?: string
  role?: 'admin' | 'operator' | 'viewer'
  org_id?: string
}

export const authApi = {
  login(data: LoginRequest): Promise<LoginResponse> {
    const formData = new URLSearchParams()
    formData.append('username', data.username)
    formData.append('password', data.password)

    return request.post('/auth/login', formData, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    })
  },

  register(data: RegisterRequest): Promise<User> {
    return request.post('/auth/register', data)
  },

  getCurrentUser(): Promise<User> {
    return request.get('/auth/me')
  },

  logout(): Promise<void> {
    return request.post('/auth/logout')
  }
}
