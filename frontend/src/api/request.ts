import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

// 生产环境使用完整 API URL，开发环境使用代理
const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''

const instance: AxiosInstance = axios.create({
  baseURL: `${apiBaseUrl}/api/v1`,
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

  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return instance.delete(url, config)
  }
}

export default instance
