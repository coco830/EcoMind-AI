<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { authApi } from '@/api/auth'

const router = useRouter()
const route = useRoute()

const heroVideo = new URL('../../b9cd519152bcc8dc1c0b183e7806f631_raw.mp4', import.meta.url).href

const loading = ref(false)
const verifying = ref(true)
const tokenValid = ref(false)
const tokenError = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const resetSuccess = ref(false)
const token = ref('')

const form = reactive({
  password: '',
  confirmPassword: ''
})

const passwordLongEnough = computed(() => form.password.length >= 8)
const passwordsMatch = computed(
  () => !!form.password && !!form.confirmPassword && form.password === form.confirmPassword
)

onMounted(async () => {
  token.value = (route.query.token as string) || ''

  if (!token.value) {
    tokenError.value = '无效的重置链接'
    verifying.value = false
    return
  }

  try {
    const result = await authApi.verifyResetToken(token.value)
    tokenValid.value = result.valid
    if (!result.valid) {
      tokenError.value = result.message
    }
  } catch {
    tokenError.value = '无法验证重置链接'
  } finally {
    verifying.value = false
  }
})

const handleSubmit = async () => {
  if (!form.password) {
    ElMessage.warning('请输入新密码')
    return
  }

  if (form.password.length < 8) {
    ElMessage.warning('密码长度至少 8 个字符')
    return
  }

  if (form.password !== form.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    await authApi.resetPassword({
      token: token.value,
      new_password: form.password
    })
    resetSuccess.value = true
    ElMessage.success('密码已重置成功')
  } catch (error: any) {
    const message = error?.response?.data?.detail || '密码重置失败，请重试'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

const goToLogin = () => {
  router.push({ name: 'Login' })
}

const goToForgotPassword = () => {
  router.push({ name: 'ForgotPassword' })
}
</script>

<template>
  <div class="auth-shell">
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

    <main class="auth-stage auth-stage-compact">
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

      <section class="auth-hero" aria-label="Reset password hero">
        <span class="hero-eyebrow">Credential Reset 凭证更新</span>
        <h1 class="hero-title">为下一次安全登录设置新的凭证</h1>
        <p class="hero-subtitle-en">
          Create a stronger password and restore secure access to the platform.
        </p>
        <p class="hero-subtitle-cn">
          重新设置更安全的登录密码，恢复对平台与业务协同流程的访问。
        </p>
      </section>

      <section class="panel-shell">
        <section class="panel-card panel-card--compact" aria-labelledby="reset-title">
          <div class="panel-heading">
            <p class="panel-kicker">Reset Password</p>
            <h2 id="reset-title" class="panel-title">重置密码</h2>
            <p class="panel-description">请根据系统校验结果完成密码更新。</p>
          </div>

          <div v-if="verifying" class="status-card status-card--loading">
            <svg class="status-icon spin" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.28" />
              <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
            </svg>
            <div>
              <h2 class="status-title">正在验证重置链接</h2>
              <p class="status-text">请稍候，系统正在确认当前链接是否仍然有效。</p>
            </div>
          </div>

          <div v-else-if="!tokenValid && !resetSuccess" class="stack-actions">
            <div class="status-card status-card--error">
              <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M10.29 3.86l-7.2 12.48A2 2 0 004.82 19h14.36a2 2 0 001.73-2.66L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
              <h2 class="status-title">链接已失效或不可用</h2>
              <p class="status-text">{{ tokenError }}</p>
              <p class="status-note">你可以重新申请一封新的重置邮件，再通过新链接完成密码设置。</p>
            </div>

            <button class="submit-button" type="button" @click="goToForgotPassword">
              <span class="button-content">
                重新申请重置链接
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
                </svg>
              </span>
            </button>

            <button class="secondary-button" type="button" @click="goToLogin">
              <span class="button-content">返回登录</span>
            </button>
          </div>

          <div v-else-if="resetSuccess" class="stack-actions">
            <div class="status-card status-card--success">
              <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4" />
                <circle cx="12" cy="12" r="9" />
              </svg>
              <h2 class="status-title">密码已更新</h2>
              <p class="status-text">新密码已经生效，现在可以使用新的凭证重新登录平台。</p>
            </div>

            <button class="submit-button" type="button" @click="goToLogin">
              <span class="button-content">
                前往登录
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
                </svg>
              </span>
            </button>
          </div>

          <form v-else class="glass-form" @submit.prevent="handleSubmit">
            <label class="field-group" for="password">
              <span class="field-label">新密码</span>
              <div class="toggle-field">
                <input
                  id="password"
                  v-model="form.password"
                  class="glass-input"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="请输入新密码"
                  autocomplete="new-password"
                  required
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
            </label>

            <label class="field-group" for="confirmPassword">
              <span class="field-label">确认新密码</span>
              <div class="toggle-field">
                <input
                  id="confirmPassword"
                  v-model="form.confirmPassword"
                  class="glass-input"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  placeholder="请再次输入新密码"
                  autocomplete="new-password"
                  required
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
            </label>

            <div class="criteria-list">
              <div class="criteria-item" :class="{ 'is-met': passwordLongEnough }">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path v-if="passwordLongEnough" stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  <path v-else stroke-linecap="round" stroke-linejoin="round" d="M12 6v12M6 12h12" />
                </svg>
                <span>至少 8 个字符</span>
              </div>

              <div class="criteria-item" :class="{ 'is-met': passwordsMatch }">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path v-if="passwordsMatch" stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  <path v-else stroke-linecap="round" stroke-linejoin="round" d="M12 6v12M6 12h12" />
                </svg>
                <span>两次输入保持一致</span>
              </div>
            </div>

            <button
              class="submit-button"
              type="submit"
              :disabled="loading || !passwordLongEnough || !passwordsMatch"
            >
              <span v-if="loading" class="button-content">
                <svg class="spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.28" />
                  <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
                </svg>
                重置中...
              </span>
              <span v-else class="button-content">
                保存新密码
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
                </svg>
              </span>
            </button>

            <div class="panel-footer">
              <span>需要重新申请邮件？</span>
              <a class="text-link" href="#" @click.prevent="goToForgotPassword">返回找回密码</a>
            </div>
          </form>
        </section>
      </section>
    </main>
  </div>
</template>

<style scoped>
@import '../styles/auth-glass-page.css';
</style>
