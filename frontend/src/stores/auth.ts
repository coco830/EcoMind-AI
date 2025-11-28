import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type User, type LoginRequest } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))

  const isAuthenticated = computed(() => !!token.value)

  async function login(credentials: LoginRequest) {
    const response = await authApi.login(credentials)
    token.value = response.access_token
    user.value = response.user
    localStorage.setItem('token', response.access_token)
    return response
  }

  async function logout() {
    await authApi.logout()
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  async function fetchUser() {
    if (!token.value) return
    try {
      user.value = await authApi.getCurrentUser()
    } catch {
      logout()
    }
  }

  return {
    user,
    token,
    isAuthenticated,
    login,
    logout,
    fetchUser
  }
})
