<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const authStore = useAuthStore()

const passwordForm = ref({
  currentPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const handlePasswordChange = () => {
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }

  if (passwordForm.value.newPassword.length < 8) {
    ElMessage.error('密码长度至少8位')
    return
  }

  // TODO: Call API to change password
  ElMessage.success('密码修改成功')
  passwordForm.value = {
    currentPassword: '',
    newPassword: '',
    confirmPassword: ''
  }
}
</script>

<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card>
          <template #header>
            <span>个人信息</span>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="用户名">
              {{ authStore.user?.username || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="邮箱">
              {{ authStore.user?.email || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="姓名">
              {{ authStore.user?.full_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="角色">
              <el-tag>{{ authStore.user?.role || '-' }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="注册时间">
              {{ authStore.user?.created_at ? new Date(authStore.user.created_at).toLocaleString() : '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card>
          <template #header>
            <span>修改密码</span>
          </template>
          <el-form label-width="100px">
            <el-form-item label="当前密码">
              <el-input
                v-model="passwordForm.currentPassword"
                type="password"
                show-password
                placeholder="请输入当前密码"
              />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input
                v-model="passwordForm.newPassword"
                type="password"
                show-password
                placeholder="请输入新密码（至少8位）"
              />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input
                v-model="passwordForm.confirmPassword"
                type="password"
                show-password
                placeholder="请再次输入新密码"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handlePasswordChange">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="system-info" style="margin-top: 20px">
      <template #header>
        <span>系统信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="系统名称">EcoMind-AI</el-descriptions-item>
        <el-descriptions-item label="版本号">v1.0.0</el-descriptions-item>
        <el-descriptions-item label="系统描述">智慧环保SaaS平台</el-descriptions-item>
        <el-descriptions-item label="技术栈">Vue 3 + FastAPI + TDengine</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 1200px;
}

/* 主按钮 - 深蓝色 #0B1727 */
:deep(.el-button--primary) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
  color: #fff !important;
}

:deep(.el-button--primary:hover),
:deep(.el-button--primary:focus) {
  background-color: #162a3d !important;
  border-color: #162a3d !important;
}

:deep(.el-button--primary:active) {
  background-color: #0a1320 !important;
  border-color: #0a1320 !important;
}
</style>
