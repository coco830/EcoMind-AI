<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'

import { authApi } from '@/api/auth'

const router = useRouter()

const heroVideo = new URL('../../b9cd519152bcc8dc1c0b183e7806f631_raw.mp4', import.meta.url).href

const loading = ref(false)
const submitted = ref(false)

const form = reactive({
  email: ''
})

const handleSubmit = async () => {
  if (!form.email.trim()) {
    ElMessage.warning('请输入邮箱地址')
    return
  }

  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(form.email)) {
    ElMessage.warning('请输入有效的邮箱地址')
    return
  }

  loading.value = true
  try {
    await authApi.forgotPassword({ email: form.email.trim() })
    submitted.value = true
    ElMessage.success('如果邮箱已注册，系统将发送密码重置邮件')
  } catch {
    submitted.value = true
    ElMessage.success('如果邮箱已注册，系统将发送密码重置邮件')
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

      <section class="auth-hero" aria-label="Forgot password hero">
        <span class="hero-eyebrow">Account Recovery 账号找回</span>
        <h1 class="hero-title">快速取回你的平台访问权限</h1>
        <p class="hero-subtitle-en">
          Recover access without interrupting your environmental operations.
        </p>
        <p class="hero-subtitle-cn">
          在不中断企业环保协同工作的前提下，安全找回平台访问权限。
        </p>
      </section>

      <section class="panel-shell">
        <section class="panel-card panel-card--compact" aria-labelledby="forgot-title">
          <div class="panel-heading">
            <p class="panel-kicker">Forgot Password</p>
            <h2 id="forgot-title" class="panel-title">忘记密码</h2>
            <p class="panel-description panel-description--compact">
              输入注册邮箱后，系统将向对应地址发送重置密码链接
            </p>
          </div>

          <div v-if="submitted" class="stack-actions">
            <div class="status-card status-card--success">
              <svg class="status-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M4 7l7.2 5.4a1.4 1.4 0 001.6 0L20 7" />
                <rect x="3" y="5" width="18" height="14" rx="3" />
              </svg>
              <h2 class="status-title">邮件发送请求已提交</h2>
              <p class="status-text">
                如果 <strong>{{ form.email }}</strong> 是已注册邮箱，系统将向该地址发送密码重置邮件。
              </p>
              <p class="status-note">请检查收件箱与垃圾邮件文件夹，重置链接通常会在 30 分钟内失效。</p>
            </div>

            <button class="submit-button" type="button" @click="goToLogin">
              <span class="button-content">
                返回登录
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
                </svg>
              </span>
            </button>
          </div>

          <form v-else class="glass-form" @submit.prevent="handleSubmit">
            <label class="field-group" for="email">
              <span class="field-label">Email 邮箱</span>
              <input
                id="email"
                v-model="form.email"
                class="glass-input"
                type="email"
                placeholder="请输入注册邮箱"
                autocomplete="email"
                required
              />
              <p class="field-hint">为了安全起见，无论邮箱是否存在，页面都会返回统一提示。</p>
            </label>

            <button class="submit-button" type="submit" :disabled="loading">
              <span v-if="loading" class="button-content">
                <svg class="spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.28" />
                  <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
                </svg>
                发送中...
              </span>
              <span v-else class="button-content">
                发送重置链接
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
                </svg>
              </span>
            </button>

            <div class="panel-footer">
              <span>记起密码了？</span>
              <a class="text-link" href="#" @click.prevent="goToLogin">返回登录</a>
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
