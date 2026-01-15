import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type User, type LoginRequest } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const token = ref<string | null>(localStorage.getItem('token'))

  const isAuthenticated = computed(() => !!token.value)

  // 权限计算属性
  const isSuperAdmin = computed(() => user.value?.is_superadmin ?? false)
  const isDocEditor = computed(() =>
    user.value?.is_superadmin || user.value?.role === 'doc_editor'
  )
  const isViewer = computed(() => user.value?.role === 'viewer')

  // 功能权限
  const canEditDocuments = computed(() => isDocEditor.value)  // 可编辑文档数据
  const canDeleteDocuments = computed(() => isSuperAdmin.value)  // 仅超管可删除
  const canManageInvitations = computed(() => isSuperAdmin.value)  // 仅超管可管理邀请码
  const canManageDevices = computed(() => isSuperAdmin.value)  // 仅超管可管理设备
  const canManageUsers = computed(() => isSuperAdmin.value)  // 仅超管可管理用户

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
    // 权限
    isSuperAdmin,
    isDocEditor,
    isViewer,
    canEditDocuments,
    canDeleteDocuments,
    canManageInvitations,
    canManageDevices,
    canManageUsers,
    // 方法
    login,
    logout,
    fetchUser
  }
})
