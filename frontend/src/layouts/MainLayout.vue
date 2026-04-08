<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  HomeFilled,
  Monitor,
  DataLine,
  Bell,
  VideoCamera,
  Document,
  Setting,
  ArrowDown,
  Ticket,
  FolderOpened
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const isCollapse = ref(false)

// 基础菜单项
const baseMenuItems = [
  { path: '/', icon: HomeFilled, title: '监控驾驶舱' },
  { path: '/devices', icon: Monitor, title: '设备管理' },
  { path: '/data', icon: DataLine, title: '数据查询' },
  { path: '/alarms', icon: Bell, title: '告警管理' },
  { path: '/video', icon: VideoCamera, title: '视频联动' },
  { path: '/reports', icon: Document, title: '报表中心' },
  { path: '/self-inspection', icon: FolderOpened, title: '文档数据' },
  { path: '/settings', icon: Setting, title: '系统设置' }
]

// 超级管理员专属菜单
const superAdminMenuItems = [
  { path: '/invitations', icon: Ticket, title: '邀请码管理' }
]

const regulatorMenuItems = [
  { path: '/regulator', icon: HomeFilled, title: '监管驾驶舱' },
  { path: '/regulator/reports', icon: Document, title: '监管文档' }
]

// 根据用户权限动态生成菜单
const menuItems = computed(() => {
  if (authStore.user?.role === 'regulator') {
    return regulatorMenuItems
  }
  if (authStore.user?.is_superadmin) {
    return [...baseMenuItems, ...regulatorMenuItems, ...superAdminMenuItems]
  }
  return baseMenuItems
})

const activeMenu = computed(() => route.path)

const handleLogout = async () => {
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <el-container class="layout-container">
    <el-aside :width="isCollapse ? '72px' : '220px'" class="aside">
      <!-- Logo Section -->
      <div class="logo">
        <svg viewBox="0 0 89 95" fill="none" xmlns="http://www.w3.org/2000/svg" class="logo-svg">
          <g fill="currentColor">
            <path d="M51 14 L44 23 L38 34 L40 35 L49 20 L51 19 L55 23 L66 40 L70 50 L70 59 L67 65 L62 70 L56 73 L47 73 L46 75 L56 75 L63 72 L70 65 L72 60 L71 46 L66 36 Z" />
            <path d="M16 32 L15 33 L15 48 L18 55 L25 62 L35 65 L39 70 L38 64 L35 57 L31 51 L23 43 L25 42 L31 46 L38 53 L43 61 L44 59 L44 48 L43 46 L35 38 Z" />
            <path d="M65 53 L63 53 L61 60 L54 66 L55 67 L59 66 L62 63 L65 58 Z" />
          </g>
        </svg>
        <span v-show="!isCollapse" class="logo-text">YueenEcoMind-AI</span>
      </div>

      <!-- Navigation Menu -->
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :router="true"
        class="menu"
        background-color="#0B1727"
        text-color="rgba(255,255,255,0.65)"
        active-text-color="#ffffff"
      >
        <el-menu-item
          v-for="item in menuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.title }}</template>
        </el-menu-item>
      </el-menu>

      <!-- Collapse Toggle -->
      <div class="collapse-toggle" @click="isCollapse = !isCollapse">
        <svg v-if="isCollapse" class="toggle-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
        </svg>
        <svg v-else class="toggle-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
        </svg>
      </div>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <h1 class="page-title">{{ menuItems.find(item => item.path === activeMenu)?.title || '监控驾驶舱' }}</h1>
        </div>
        <div class="header-right">
          <el-dropdown trigger="click">
            <span class="user-dropdown">
              <div class="user-avatar">
                <svg class="avatar-icon" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                </svg>
              </div>
              <span class="username">{{ authStore.user?.username || '用户' }}</span>
              <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/settings')">
                  个人设置
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <RouterView />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-container {
  height: 100vh;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
}

.aside {
  background-color: #0B1727;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Logo Section */
.logo {
  height: 72px;
  display: flex;
  align-items: center;
  padding: 0 18px;
  gap: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.logo-svg {
  width: 32px;
  height: 32px;
  min-width: 32px;
  color: #ffffff;
}

.logo-text {
  font-size: 15px;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
  letter-spacing: -0.01em;
}

/* Menu Styles */
.menu {
  border-right: none;
  flex: 1;
  padding: 12px 8px;
}

.menu:not(.el-menu--collapse) {
  width: 100%;
}

:deep(.el-menu-item) {
  height: 44px;
  line-height: 44px;
  margin: 4px 0;
  border-radius: 10px;
  transition: all 0.2s ease;
}

:deep(.el-menu-item:hover) {
  background-color: rgba(255, 255, 255, 0.08) !important;
}

:deep(.el-menu-item.is-active) {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.12) 0%, rgba(255, 255, 255, 0.06) 100%) !important;
  font-weight: 500;
}

:deep(.el-menu-item .el-icon) {
  font-size: 18px;
  margin-right: 12px;
}

:deep(.el-menu--collapse .el-menu-item) {
  padding: 0 !important;
  justify-content: center;
}

:deep(.el-menu--collapse .el-menu-item .el-icon) {
  margin-right: 0;
}

/* Collapse Toggle */
.collapse-toggle {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  transition: background-color 0.2s ease;
}

.collapse-toggle:hover {
  background-color: rgba(255, 255, 255, 0.04);
}

.toggle-icon {
  width: 18px;
  height: 18px;
  color: rgba(255, 255, 255, 0.5);
}

/* Header Styles */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: #ffffff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  height: 64px;
}

.header-left {
  display: flex;
  align-items: center;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #1D1D1F;
  margin: 0;
  letter-spacing: -0.02em;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-dropdown {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 6px 12px;
  border-radius: 12px;
  transition: background-color 0.2s ease;
}

.user-dropdown:hover {
  background-color: #F5F5F7;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: linear-gradient(135deg, #0B1727 0%, #1a2d42 100%);
  display: flex;
  align-items: center;
  justify-content: center;
}

.avatar-icon {
  width: 18px;
  height: 18px;
  color: #ffffff;
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: #1D1D1F;
}

.dropdown-arrow {
  font-size: 12px;
  color: #86868B;
}

/* Main Content */
.main {
  background: #F5F5F7;
  padding: 24px;
  overflow-y: auto;
}

/* Scrollbar */
.main::-webkit-scrollbar {
  width: 6px;
}

.main::-webkit-scrollbar-track {
  background: transparent;
}

.main::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

.main::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
