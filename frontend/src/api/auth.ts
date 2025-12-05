import { request } from './request'

export interface InvitationCodeValidation {
  valid: boolean
  code: string
  name: string
  remaining_uses: number
  expires_at: string | null
}

export interface User {
  id: string
  username: string
  email: string
  full_name: string | null
  role: 'admin' | 'operator' | 'viewer'
  is_active: boolean
  is_superadmin: boolean
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
  invitation_code: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ForgotPasswordResponse {
  message: string
  success: boolean
}

export interface ResetPasswordRequest {
  token: string
  new_password: string
}

export interface ResetPasswordResponse {
  message: string
  success: boolean
}

export interface VerifyTokenResponse {
  valid: boolean
  message: string
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
  },

  validateInvitationCode(code: string): Promise<InvitationCodeValidation> {
    return request.get(`/invitations/validate/${code}`)
  },

  forgotPassword(data: ForgotPasswordRequest): Promise<ForgotPasswordResponse> {
    return request.post('/auth/forgot-password', data)
  },

  resetPassword(data: ResetPasswordRequest): Promise<ResetPasswordResponse> {
    return request.post('/auth/reset-password', data)
  },

  verifyResetToken(token: string): Promise<VerifyTokenResponse> {
    return request.get(`/auth/verify-reset-token?token=${token}`)
  }
}
