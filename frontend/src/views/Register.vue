<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  full_name: ''
})

const validateConfirmPassword = (_rule: any, value: string, callback: any) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名长度 3-64 个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '用户名只能包含字母、数字和下划线', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, max: 128, message: '密码长度 8-128 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' }
  ],
  full_name: [
    { max: 128, message: '姓名长度不能超过 128 个字符', trigger: 'blur' }
  ]
}

const handleRegister = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authApi.register({
      username: form.username,
      email: form.email,
      password: form.password,
      full_name: form.full_name || undefined
    })

    ElMessage.success('注册成功！请登录')
    router.push({ name: 'Login' })
  } catch (error: any) {
    const message = error?.response?.data?.detail || '注册失败，请重试'
    if (typeof message === 'string') {
      ElMessage.error(message)
    } else if (Array.isArray(message)) {
      // 处理验证错误数组
      const firstError = message[0]
      ElMessage.error(firstError?.msg || '注册失败，请检查输入')
    } else {
      ElMessage.error('注册失败，请重试')
    }
  } finally {
    loading.value = false
  }
}

const goToLogin = () => {
  router.push({ name: 'Login' })
}
</script>

<template>
  <div class="register-container">
    <div class="register-card">
      <div class="register-header">
        <img src="/vite.svg" alt="Logo" class="logo" />
        <h1 class="title">EcoMind-AI</h1>
        <p class="subtitle">智慧环保SaaS平台 - 用户注册</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="register-form"
        @submit.prevent="handleRegister"
      >
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名（3-64个字符，仅限字母、数字、下划线）"
            prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="email">
          <el-input
            v-model="form.email"
            placeholder="邮箱地址"
            prefix-icon="Message"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="full_name">
          <el-input
            v-model="form.full_name"
            placeholder="真实姓名（可选）"
            prefix-icon="UserFilled"
            size="large"
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码（至少8个字符）"
            prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="确认密码"
            prefix-icon="Lock"
            size="large"
            show-password
            @keyup.enter="handleRegister"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="register-btn"
            @click="handleRegister"
          >
            注册
          </el-button>
        </el-form-item>
      </el-form>

      <div class="register-footer">
        <p>
          已有账号？
          <el-link type="primary" @click="goToLogin">立即登录</el-link>
        </p>
        <p class="tip">注册后将自动分配到默认组织</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-card {
  width: 450px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.register-header {
  text-align: center;
  margin-bottom: 30px;
}

.logo {
  width: 60px;
  height: 60px;
  margin-bottom: 16px;
}

.title {
  font-size: 28px;
  color: #333;
  margin: 0 0 8px;
}

.subtitle {
  color: #999;
  margin: 0;
  font-size: 14px;
}

.register-form {
  margin-top: 20px;
}

.register-btn {
  width: 100%;
}

.register-footer {
  margin-top: 20px;
  text-align: center;
  color: #999;
  font-size: 14px;
}

.register-footer p {
  margin: 8px 0;
}

.register-footer .tip {
  font-size: 12px;
  color: #67c23a;
}
</style>
