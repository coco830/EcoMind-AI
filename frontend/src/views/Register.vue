<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { authApi } from '@/api/auth'
import { apiBasePath } from '@/api/request'

const router = useRouter()

const heroVideo = new URL('../../b9cd519152bcc8dc1c0b183e7806f631_raw.mp4', import.meta.url).href

const loading = ref(false)
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const invitationValid = ref(false)
const invitationName = ref('')
const checkingCode = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  full_name: '',
  invitation_code: ''
})

const errors = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
  full_name: '',
  invitation_code: ''
})

watch(
  () => form.invitation_code,
  () => {
    invitationValid.value = false
    invitationName.value = ''
    if (errors.invitation_code) {
      errors.invitation_code = ''
    }
  }
)

const validateInvitationCode = async () => {
  if (!form.invitation_code.trim()) {
    invitationValid.value = false
    invitationName.value = ''
    return
  }

  checkingCode.value = true
  try {
    const response = await fetch(
      `${apiBasePath}/invitations/validate/${encodeURIComponent(form.invitation_code.trim())}`
    )
    const data = await response.json()

    if (data.valid) {
      invitationValid.value = true
      invitationName.value = data.name
      errors.invitation_code = ''
    } else {
      invitationValid.value = false
      invitationName.value = ''
      errors.invitation_code = data.message || '邀请码无效'
    }
  } catch {
    invitationValid.value = false
    invitationName.value = ''
    errors.invitation_code = '验证邀请码失败'
  } finally {
    checkingCode.value = false
  }
}

const validateForm = (): boolean => {
  let isValid = true

  errors.username = ''
  errors.email = ''
  errors.password = ''
  errors.confirmPassword = ''
  errors.full_name = ''
  errors.invitation_code = ''

  if (!form.invitation_code.trim()) {
    errors.invitation_code = '请输入邀请码'
    isValid = false
  } else if (!invitationValid.value) {
    errors.invitation_code = '请先验证邀请码'
    isValid = false
  }

  if (!form.username.trim()) {
    errors.username = '请输入用户名'
    isValid = false
  } else if (form.username.length < 3 || form.username.length > 64) {
    errors.username = '用户名长度需为 3-64 个字符'
    isValid = false
  } else if (!/^[a-zA-Z0-9_]+$/.test(form.username)) {
    errors.username = '仅支持字母、数字和下划线'
    isValid = false
  }

  if (!form.email.trim()) {
    errors.email = '请输入邮箱地址'
    isValid = false
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = '请输入有效的邮箱地址'
    isValid = false
  }

  if (!form.password) {
    errors.password = '请输入密码'
    isValid = false
  } else if (form.password.length < 8) {
    errors.password = '密码至少需要 8 个字符'
    isValid = false
  }

  if (!form.confirmPassword) {
    errors.confirmPassword = '请再次输入密码'
    isValid = false
  } else if (form.confirmPassword !== form.password) {
    errors.confirmPassword = '两次密码输入不一致'
    isValid = false
  }

  if (form.full_name.trim() && form.full_name.trim().length > 128) {
    errors.full_name = '真实姓名不能超过 128 个字符'
    isValid = false
  }

  return isValid
}

const handleRegister = async () => {
  if (!validateForm()) return

  loading.value = true
  try {
    await authApi.register({
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      full_name: form.full_name.trim() || undefined,
      invitation_code: form.invitation_code.trim()
    })

    ElMessage.success('注册成功，请登录平台')
    router.push({ name: 'Login' })
  } catch (error: any) {
    const message = error?.response?.data?.detail || '注册失败，请重试'

    if (typeof message === 'string') {
      ElMessage.error(message)
    } else if (Array.isArray(message)) {
      ElMessage.error(message[0]?.msg || '注册失败，请检查输入')
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
  <div class="auth-shell auth-shell--hero-center">
    <div class="video-layer" aria-hidden="true">
      <video
        class="login-video"
        :src="heroVideo"
        autoplay
        muted
        loop
        playsinline
        preload="metadata"
      ></video>
      <div class="video-tint"></div>
      <div class="video-vignette"></div>
      <div class="glass-wash"></div>
      <div class="ambient ambient-one"></div>
      <div class="ambient ambient-two"></div>
      <div class="ambient ambient-three"></div>
    </div>

    <main class="auth-stage">
      <header class="auth-header">
        <div class="brand-chip" aria-label="Company brand">
          <div class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 89 95" fill="none" xmlns="http://www.w3.org/2000/svg">
              <g fill="currentColor">
                <path d="M51 14 L44 23 L38 34 L40 35 L49 20 L51 19 L55 23 L66 40 L70 50 L70 59 L67 65 L62 70 L56 73 L47 73 L46 75 L56 75 L63 72 L70 65 L72 60 L71 46 L66 36 Z" />
                <path d="M16 32 L15 33 L15 48 L18 55 L25 62 L35 65 L39 70 L38 64 L35 57 L31 51 L23 43 L25 42 L31 46 L38 53 L43 61 L44 59 L44 48 L43 46 L35 38 Z" />
                <path d="M65 53 L63 53 L61 60 L54 66 L55 67 L59 66 L62 63 L65 58 Z" />
              </g>
            </svg>
          </div>
          <div class="brand-copy">
            <span class="brand-name-en">
              Yunnan yueen Environmental Protection Technology Consulting Co.Ltd
            </span>
            <span class="brand-name-cn">云南悦恩环保技术咨询有限公司</span>
          </div>
        </div>

        <a class="header-link" href="#" @click.prevent="goToLogin">返回登录</a>
      </header>

      <section class="auth-hero" aria-label="Register hero">
        <span class="hero-eyebrow">Enterprise Onboarding 企业接入</span>
        <h1 class="hero-title">从创建账户开始，让环保协同更流畅</h1>
        <p class="hero-subtitle-en">
          Build a trusted access point for teams, devices and evidence workflows.
        </p>
        <p class="hero-subtitle-cn">
          为团队、设备、告警与留痕流程建立统一可信的接入入口。
        </p>

        <div class="hero-note">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01" />
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.29 3.86l-7.2 12.48A2 2 0 004.82 19h14.36a2 2 0 001.73-2.66L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
          需要有效邀请码才能完成注册，请联系超级管理员或实施团队获取。
        </div>
      </section>

      <section class="panel-shell">
        <section class="panel-card panel-card--scroll" aria-labelledby="register-title">
          <div class="panel-heading">
            <p class="panel-kicker">Create Account</p>
            <h2 id="register-title" class="panel-title">创建账户</h2>
            <p class="panel-description">加入 YueenEcoMind-AI 智慧环保平台</p>
          </div>

          <form class="glass-form" @submit.prevent="handleRegister">
            <label class="field-group" for="invitation_code">
              <span class="field-label">邀请码</span>
              <div class="action-field">
                <input
                  id="invitation_code"
                  v-model="form.invitation_code"
                  class="glass-input"
                  :class="{
                    'input-invalid': !!errors.invitation_code,
                    'input-valid': invitationValid
                  }"
                  type="text"
                  placeholder="请输入邀请码，如 XXXX-XXXX-XXXX"
                  autocomplete="off"
                  @blur="validateInvitationCode"
                />
                <button
                  class="field-action"
                  type="button"
                  :disabled="checkingCode || !form.invitation_code.trim()"
                  @click="validateInvitationCode"
                >
                  <span v-if="checkingCode">验证中...</span>
                  <span v-else-if="invitationValid">已验证</span>
                  <span v-else>验证</span>
                </button>
              </div>
              <p v-if="errors.invitation_code" class="field-error">{{ errors.invitation_code }}</p>
              <p v-else-if="invitationValid && invitationName" class="field-success">
                企业主体：{{ invitationName }}
              </p>
            </label>

            <label class="field-group" for="username">
              <span class="field-label">用户名</span>
              <input
                id="username"
                v-model="form.username"
                class="glass-input"
                :class="{ 'input-invalid': !!errors.username }"
                type="text"
                placeholder="3-64 个字符，仅支持字母、数字和下划线"
                autocomplete="username"
              />
              <p v-if="errors.username" class="field-error">{{ errors.username }}</p>
            </label>

            <label class="field-group" for="email">
              <span class="field-label">邮箱地址</span>
              <input
                id="email"
                v-model="form.email"
                class="glass-input"
                :class="{ 'input-invalid': !!errors.email }"
                type="email"
                placeholder="your@email.com"
                autocomplete="email"
              />
              <p v-if="errors.email" class="field-error">{{ errors.email }}</p>
            </label>

            <label class="field-group" for="full_name">
              <span class="field-label">
                真实姓名
                <span class="field-label-muted">可选</span>
              </span>
              <input
                id="full_name"
                v-model="form.full_name"
                class="glass-input"
                :class="{ 'input-invalid': !!errors.full_name }"
                type="text"
                placeholder="请输入联系人姓名"
                autocomplete="name"
              />
              <p v-if="errors.full_name" class="field-error">{{ errors.full_name }}</p>
            </label>

            <label class="field-group" for="password">
              <span class="field-label">密码</span>
              <div class="toggle-field">
                <input
                  id="password"
                  v-model="form.password"
                  class="glass-input"
                  :class="{ 'input-invalid': !!errors.password }"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="至少 8 个字符"
                  autocomplete="new-password"
                />
                <button
                  class="icon-button"
                  type="button"
                  :aria-label="showPassword ? '隐藏密码' : '显示密码'"
                  @click="showPassword = !showPassword"
                >
                  <svg
                    v-if="!showPassword"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <svg
                    v-else
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 3l18 18" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M10.585 10.587a2 2 0 102.828 2.828" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9.88 5.09A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a9.967 9.967 0 01-4.13 5.411M6.228 6.229A9.956 9.956 0 002.458 12c1.274 4.057 5.065 7 9.542 7a9.95 9.95 0 005.09-1.397" />
                  </svg>
                </button>
              </div>
              <p v-if="errors.password" class="field-error">{{ errors.password }}</p>
              <p v-else class="field-hint">建议使用包含字母、数字和符号的高强度密码。</p>
            </label>

            <label class="field-group" for="confirmPassword">
              <span class="field-label">确认密码</span>
              <div class="toggle-field">
                <input
                  id="confirmPassword"
                  v-model="form.confirmPassword"
                  class="glass-input"
                  :class="{ 'input-invalid': !!errors.confirmPassword }"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  placeholder="再次输入密码"
                  autocomplete="new-password"
                  @keyup.enter="handleRegister"
                />
                <button
                  class="icon-button"
                  type="button"
                  :aria-label="showConfirmPassword ? '隐藏确认密码' : '显示确认密码'"
                  @click="showConfirmPassword = !showConfirmPassword"
                >
                  <svg
                    v-if="!showConfirmPassword"
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <svg
                    v-else
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="1.8"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M3 3l18 18" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M10.585 10.587a2 2 0 102.828 2.828" />
                    <path stroke-linecap="round" stroke-linejoin="round" d="M9.88 5.09A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a9.967 9.967 0 01-4.13 5.411M6.228 6.229A9.956 9.956 0 002.458 12c1.274 4.057 5.065 7 9.542 7a9.95 9.95 0 005.09-1.397" />
                  </svg>
                </button>
              </div>
              <p v-if="errors.confirmPassword" class="field-error">{{ errors.confirmPassword }}</p>
            </label>

            <button class="submit-button" type="submit" :disabled="loading">
              <span v-if="loading" class="button-content">
                <svg class="spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.28" />
                  <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
                </svg>
                注册中...
              </span>
              <span v-else class="button-content">
                创建账户
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
                </svg>
              </span>
            </button>
          </form>

          <div class="panel-footer">
            <span>已有账号？</span>
            <a class="text-link" href="#" @click.prevent="goToLogin">立即登录</a>
          </div>
        </section>
      </section>
    </main>
  </div>
</template>

<style scoped>
@import '../styles/auth-glass-page.css';
</style>
