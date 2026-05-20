import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

const normalizeBaseUrl = (url: string) => url.replace(/\/+$/, '')

// If the page is served over HTTPS but the configured API uses HTTP, upgrade to HTTPS to avoid mixed content.
const ensureHttps = (url: string) => {
  if (typeof window !== 'undefined' && window.location.protocol === 'https:' && url.startsWith('http://')) {
    return url.replace(/^http:\/\//i, 'https://')
  }
  return url
}

const rawApiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '').trim()
export const resolvedApiBaseUrl = normalizeBaseUrl(ensureHttps(rawApiBaseUrl))
export const apiBasePath = resolvedApiBaseUrl ? `${resolvedApiBaseUrl}/api/v1` : '/api/v1'

const instance: AxiosInstance = axios.create({
  baseURL: apiBasePath,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
instance.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
instance.interceptors.response.use(
  (response: AxiosResponse) => {
    return response.data
  },
  (error) => {
    const message = error.response?.data?.detail || error.message || '请求失败'

    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      // 使用 hash 模式路由
      const basePath = import.meta.env.BASE_URL || '/'
      window.location.href = `${basePath}#/login`
    } else {
      ElMessage.error(message)
    }

    return Promise.reject(error)
  }
)

export const request = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.get(url, config)
  },

  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.post(url, data, config)
  },

  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.put(url, data, config)
  },

  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return instance.patch(url, data, config)
  },

  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete(url, config)
  }
}

export default instance
