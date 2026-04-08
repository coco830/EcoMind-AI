<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const heroVideo = new URL('../../b9cd519152bcc8dc1c0b183e7806f631_raw.mp4', import.meta.url).href

const loading = ref(false)
const showPassword = ref(false)
const rememberMe = ref(false)
const showLoginModal = ref(false)
const usernameInputRef = ref<HTMLInputElement | null>(null)

const form = reactive({
  username: '',
  password: ''
})

const focusUsernameInput = async () => {
  await nextTick()
  usernameInputRef.value?.focus()
}

const openLoginModal = async () => {
  showLoginModal.value = true
  await focusUsernameInput()
}

const closeLoginModal = () => {
  showLoginModal.value = false
  showPassword.value = false
}

const handleKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && showLoginModal.value) {
    closeLoginModal()
  }
}

onMounted(() => {
  const savedUsername = localStorage.getItem('ecomind_username')
  const savedRemember = localStorage.getItem('ecomind_remember')

  localStorage.removeItem('ecomind_password')

  if (savedRemember === 'true' && savedUsername) {
    form.username = savedUsername
    rememberMe.value = true
  }

  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
})

const handleLogin = async () => {
  if (!form.username.trim()) {
    ElMessage.warning('请输入用户名或邮箱')
    return
  }

  if (!form.password) {
    ElMessage.warning('请输入密码')
    return
  }

  if (form.password.length < 8) {
    ElMessage.warning('密码长度至少8个字符')
    return
  }

  loading.value = true

  try {
    await authStore.login({
      username: form.username.trim(),
      password: form.password
    })

    if (rememberMe.value) {
      localStorage.setItem('ecomind_username', form.username.trim())
      localStorage.setItem('ecomind_remember', 'true')
    } else {
      localStorage.removeItem('ecomind_username')
      localStorage.removeItem('ecomind_remember')
    }

    localStorage.removeItem('ecomind_password')
    closeLoginModal()
    ElMessage.success('登录成功')

    const redirect = route.query.redirect as string
    router.push(redirect || '/')
  } catch {
    ElMessage.error('登录失败，请检查用户名/邮箱和密码')
  } finally {
    loading.value = false
  }
}

const goToRegister = () => {
  closeLoginModal()
  router.push({ name: 'Register' })
}

const goToForgotPassword = () => {
  closeLoginModal()
  router.push({ name: 'ForgotPassword' })
}
</script>

<template>
  <div class="login-shell">
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

    <main class="landing-stage">
      <header class="landing-header">
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
      </header>

      <section class="hero-content" aria-label="Marketing hero">
        <span class="hero-eyebrow">YueenEcoMind-AI企业环保智慧中台</span>
        <h1 class="hero-title">让风险在发生之前被看见</h1>
        <p class="hero-subtitle-en">Empowering a greener future through intelligence.</p>
        <p class="hero-subtitle-cn">通过智慧力量推动更绿色的未来</p>

        <div class="hero-actions">
          <button class="primary-cta" type="button" @click="openLoginModal">
            <span class="cta-balance" aria-hidden="true"></span>
            <span class="cta-label">进入平台</span>
            <span class="cta-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
              </svg>
            </span>
          </button>
        </div>
      </section>
    </main>

    <transition name="modal-fade">
      <div
        v-if="showLoginModal"
        class="modal-layer"
        role="presentation"
        @click.self="closeLoginModal"
      >
        <section
          class="login-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="login-modal-title"
        >
          <button
            type="button"
            class="modal-close"
            aria-label="关闭登录窗口"
            @click.prevent.stop="closeLoginModal"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>

          <div class="modal-heading">
            <p class="modal-kicker">Welcome Back</p>
            <h2 id="login-modal-title" class="modal-title">登录平台</h2>
          </div>

          <form class="login-form" @submit.prevent="handleLogin">
            <label class="field-group" for="username">
              <span class="field-label">Username / Email 用户名或邮箱</span>
              <input
                id="username"
                ref="usernameInputRef"
                v-model="form.username"
                class="glass-input"
                name="username"
                type="text"
                placeholder="Username / Email 用户名或邮箱"
                autocomplete="username"
                required
              />
            </label>

            <label class="field-group" for="password">
              <span class="field-label">Password 密码</span>
              <span class="password-wrap">
                <input
                  id="password"
                  v-model="form.password"
                  class="glass-input"
                  name="password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="Password 密码"
                  autocomplete="current-password"
                  required
                  @keyup.enter="handleLogin"
                />
                <button
                  type="button"
                  class="password-toggle"
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
              </span>
            </label>

            <div class="form-meta">
              <label class="remember-control">
                <input v-model="rememberMe" class="remember-native" type="checkbox" />
                <span class="remember-box">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </span>
                <span class="remember-text">记住账号</span>
              </label>

              <a class="forgot-link" href="#" @click.prevent="goToForgotPassword">忘记密码？</a>
            </div>

            <button class="submit-button" type="submit" :disabled="loading">
              <span v-if="loading" class="button-content">
                <svg class="spin" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="3" opacity="0.28" />
                  <path d="M21 12a9 9 0 00-9-9" stroke="currentColor" stroke-width="3" stroke-linecap="round" />
                </svg>
                登录中...
              </span>
              <span v-else class="button-content">
                Login 登录
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M7 17L17 7" />
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 7h8v8" />
                </svg>
              </span>
            </button>
          </form>

          <div class="modal-footer">
            <span>还没有账号？</span>
            <a href="#" @click.prevent="goToRegister">立即注册</a>
          </div>
        </section>
      </div>
    </transition>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600;700&family=Manrope:wght@400;500;600;700;800&family=Noto+Serif+SC:wght@500;600;700&display=swap');

.login-shell {
  --text-primary: rgba(255, 255, 255, 0.98);
  --text-secondary: rgba(235, 245, 255, 0.82);
  --text-muted: rgba(234, 244, 255, 0.68);
  --glass-border: rgba(255, 255, 255, 0.3);
  --glass-surface: rgba(255, 255, 255, 0.14);
  --accent-cyan: #7cd7e4;
  --accent-blue: #90b9ff;
  position: relative;
  min-height: 100dvh;
  overflow: hidden;
  background: #08111f;
  color: var(--text-primary);
  font-family: 'Manrope', sans-serif;
}

.login-shell::selection {
  background: rgba(124, 215, 228, 0.28);
  color: #ffffff;
}

.video-layer {
  position: absolute;
  inset: 0;
}

.login-video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transform: scale(1.04);
  filter: saturate(1.02) brightness(1.01);
}

.video-tint {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(180deg, rgba(8, 15, 30, 0.1), rgba(8, 15, 30, 0.04)),
    radial-gradient(circle at 50% 30%, rgba(255, 255, 255, 0.08), transparent 28%),
    radial-gradient(circle at 12% 16%, rgba(175, 228, 255, 0.12), transparent 24%);
}

.video-vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at center, transparent 54%, rgba(8, 14, 28, 0.08) 76%, rgba(8, 12, 22, 0.18) 100%);
}

.glass-wash {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), transparent 34%, rgba(255, 255, 255, 0.05) 68%, transparent 100%);
  mix-blend-mode: screen;
  opacity: 0.42;
}

.ambient {
  position: absolute;
  border-radius: 999px;
  filter: blur(60px);
  opacity: 0.4;
  pointer-events: none;
  animation: drift 14s ease-in-out infinite;
}

.ambient-one {
  top: 8%;
  right: 12%;
  width: 240px;
  height: 240px;
  background: rgba(150, 205, 255, 0.26);
}

.ambient-two {
  bottom: 10%;
  left: 8%;
  width: 260px;
  height: 260px;
  background: rgba(124, 215, 228, 0.2);
  animation-delay: -4s;
}

.ambient-three {
  top: 42%;
  left: 50%;
  width: 180px;
  height: 180px;
  background: rgba(255, 205, 214, 0.16);
  animation-delay: -9s;
}

.landing-stage {
  position: relative;
  z-index: 1;
  min-height: 100dvh;
  padding: clamp(24px, 3vw, 42px);
  display: grid;
  place-items: center;
}

.landing-header {
  position: absolute;
  top: clamp(20px, 2.6vw, 30px);
  left: clamp(20px, 2.8vw, 34px);
}

.brand-chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 11px;
  max-width: min(648px, calc(100vw - 56px));
  padding: 4px 14px 4px 9px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 999px;
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.14), rgba(255, 255, 255, 0.035)),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.24), transparent 42%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    inset 0 -1px 0 rgba(255, 255, 255, 0.04),
    0 16px 42px rgba(7, 15, 30, 0.1);
  backdrop-filter: blur(22px) saturate(1.08);
  -webkit-backdrop-filter: blur(22px) saturate(1.08);
  overflow: hidden;
}

.brand-chip::before,
.hero-eyebrow::before,
.primary-cta::before,
.submit-button::before {
  content: '';
  position: absolute;
  inset: 1px 1px auto 1px;
  height: 58%;
  border-radius: inherit;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.38), rgba(255, 255, 255, 0.02));
  pointer-events: none;
}

.brand-chip::after,
.hero-eyebrow::after,
.primary-cta::after,
.submit-button::after,
.login-modal::after,
.glass-input::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  padding: 1px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.52), rgba(255, 255, 255, 0.08) 30%, rgba(146, 206, 255, 0.28) 62%, rgba(255, 255, 255, 0.2));
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  mask-composite: exclude;
  pointer-events: none;
}

.brand-mark {
  flex: 0 0 auto;
  width: 48px;
  height: 48px;
  display: grid;
  place-items: center;
  color: #f3fbff;
  filter: drop-shadow(0 12px 26px rgba(128, 204, 255, 0.18));
}

.brand-mark svg {
  width: 36px;
  height: 36px;
}

.brand-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.brand-name-en,
.brand-name-cn {
  display: block;
  min-width: 0;
}

.brand-name-en {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.69rem;
  line-height: 1.18;
  color: rgba(250, 253, 255, 0.94);
  font-weight: 450;
  letter-spacing: 0.005em;
}

.brand-name-cn {
  font-family: 'Noto Serif SC', 'Songti SC', 'STSong', serif;
  font-size: 0.6rem;
  line-height: 1.16;
  width: 100%;
  text-align: center;
  color: rgba(235, 245, 255, 0.74);
  font-weight: 500;
  letter-spacing: 0.06em;
}

.hero-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  width: min(980px, 100%);
  text-align: center;
  padding: min(7vh, 72px) 16px 16px;
}

.hero-eyebrow {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
  padding: 11px 19px;
  border: 1px solid rgba(255, 255, 255, 0.34);
  border-radius: 999px;
  background:
    linear-gradient(160deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.015)),
    radial-gradient(circle at 18% 0%, rgba(255, 255, 255, 0.34), transparent 44%),
    radial-gradient(circle at 85% 86%, rgba(152, 212, 255, 0.16), transparent 28%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.48),
    inset 0 -1px 0 rgba(255, 255, 255, 0.04),
    0 20px 44px rgba(5, 13, 28, 0.12),
    0 0 28px rgba(158, 209, 255, 0.14);
  backdrop-filter: blur(24px) saturate(1.08);
  -webkit-backdrop-filter: blur(24px) saturate(1.08);
  color: rgba(246, 251, 255, 0.94);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.hero-title {
  margin: 32px 0 0;
  max-width: 12em;
  font-family: 'Noto Serif SC', 'Songti SC', 'STSong', 'Source Han Serif SC', serif;
  font-size: clamp(2.95rem, 5.8vw, 4.7rem);
  line-height: 1.16;
  font-weight: 600;
  letter-spacing: -0.012em;
  color: rgba(255, 255, 255, 0.98);
  text-shadow:
    0 16px 34px rgba(7, 14, 28, 0.18),
    0 0 26px rgba(255, 255, 255, 0.08);
  text-wrap: balance;
}

.hero-subtitle-en,
.hero-subtitle-cn {
  margin: 0;
  max-width: 760px;
}

.hero-subtitle-en {
  margin-top: 30px;
  font-family: 'Cormorant Garamond', serif;
  font-size: clamp(1.24rem, 2vw, 1.58rem);
  font-style: italic;
  font-weight: 600;
  letter-spacing: 0.01em;
  color: rgba(247, 251, 255, 0.94);
}

.hero-subtitle-cn {
  margin-top: 8px;
  font-family: 'Noto Serif SC', 'Songti SC', 'STSong', serif;
  font-size: clamp(0.98rem, 1.36vw, 1.12rem);
  font-weight: 500;
  line-height: 1.75;
  letter-spacing: 0.06em;
  color: rgba(234, 243, 255, 0.78);
}

.hero-actions {
  margin-top: 40px;
}

.primary-cta,
.submit-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 60px;
  padding: 0 28px;
  border: 1px solid rgba(255, 255, 255, 0.34);
  border-radius: 999px;
  background:
    linear-gradient(140deg, rgba(98, 206, 224, 0.12), rgba(146, 188, 255, 0.035)),
    radial-gradient(circle at 18% 0%, rgba(255, 255, 255, 0.38), transparent 34%),
    radial-gradient(circle at 84% 86%, rgba(150, 210, 255, 0.18), transparent 28%);
  color: #ffffff;
  font: inherit;
  font-weight: 700;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.54),
    inset 0 -1px 0 rgba(255, 255, 255, 0.04),
    0 20px 46px rgba(25, 83, 124, 0.14),
    0 0 30px rgba(151, 214, 255, 0.14);
  backdrop-filter: blur(26px) saturate(1.1);
  -webkit-backdrop-filter: blur(26px) saturate(1.1);
  cursor: pointer;
  overflow: hidden;
  touch-action: manipulation;
  transition:
    transform 220ms ease,
    box-shadow 220ms ease,
    opacity 220ms ease,
    border-color 220ms ease,
    background 220ms ease;
}

.primary-cta:hover,
.submit-button:hover {
  transform: translateY(-2px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.56),
    0 26px 52px rgba(22, 82, 124, 0.22),
    0 0 26px rgba(151, 214, 255, 0.16);
}

.primary-cta:focus-visible,
.submit-button:focus-visible,
.glass-input:focus-visible,
.password-toggle:focus-visible,
.modal-close:focus-visible {
  outline: 2px solid rgba(124, 215, 228, 0.58);
  outline-offset: 4px;
}

.primary-cta svg,
.submit-button svg {
  width: 18px;
  height: 18px;
}

.primary-cta {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr) 18px;
  column-gap: 14px;
  min-width: 176px;
  padding: 0 28px;
}

.cta-balance,
.cta-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
}

.cta-label {
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  text-align: center;
  transform: translateY(1px);
}

.cta-icon {
  opacity: 0.94;
}

.primary-cta > *,
.submit-button > * {
  position: relative;
  z-index: 1;
}

.modal-layer {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    radial-gradient(circle at center, rgba(255, 255, 255, 0.1), transparent 28%),
    linear-gradient(180deg, rgba(5, 12, 22, 0.12), rgba(5, 12, 22, 0.2));
  backdrop-filter: blur(14px) saturate(1.06);
  -webkit-backdrop-filter: blur(14px) saturate(1.06);
}

.login-modal {
  position: relative;
  width: min(420px, 100%);
  padding: 30px 26px 24px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 32px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(236, 245, 255, 0.12) 42%, rgba(128, 162, 214, 0.12) 100%),
    radial-gradient(circle at top center, rgba(255, 255, 255, 0.3), transparent 40%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.34),
    inset 0 -18px 28px rgba(62, 104, 158, 0.1),
    0 32px 90px rgba(3, 10, 23, 0.28),
    0 0 0 1px rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(28px) saturate(1.18);
  -webkit-backdrop-filter: blur(28px) saturate(1.18);
  overflow: hidden;
}

.login-modal::before {
  content: '';
  position: absolute;
  inset: 1px 1px auto 1px;
  height: 44%;
  border-radius: 30px 30px 46px 46px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0.04));
  pointer-events: none;
}

.login-modal > * {
  position: relative;
  z-index: 1;
}

.modal-close {
  position: absolute;
  top: 16px;
  right: 16px;
  z-index: 2;
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.08)),
    radial-gradient(circle at 20% 0%, rgba(255, 255, 255, 0.22), transparent 42%);
  color: rgba(244, 250, 255, 0.88);
  cursor: pointer;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.24),
    0 10px 24px rgba(11, 29, 57, 0.12);
  touch-action: manipulation;
  transition:
    transform 150ms ease,
    box-shadow 150ms ease,
    border-color 150ms ease,
    background 150ms ease;
}

.modal-close:hover {
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.34);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.1)),
    radial-gradient(circle at 20% 0%, rgba(255, 255, 255, 0.28), transparent 40%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 14px 28px rgba(11, 29, 57, 0.16);
}

.modal-close:active {
  transform: scale(0.96);
}

.modal-close svg {
  width: 18px;
  height: 18px;
}

.modal-heading {
  margin-bottom: 26px;
}

.modal-kicker {
  margin: 0 0 6px;
  font-size: 0.84rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: rgba(236, 246, 255, 0.78);
}

.modal-title {
  margin: 0;
  font-size: clamp(1.7rem, 2.2vw, 2rem);
  line-height: 1.2;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.98);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-label {
  font-size: 0.86rem;
  font-weight: 700;
  color: rgba(239, 248, 255, 0.82);
}

.password-wrap {
  position: relative;
  display: block;
}

.glass-input {
  position: relative;
  width: 100%;
  height: 58px;
  padding: 0 20px;
  border: 1px solid rgba(255, 255, 255, 0.24);
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.09)),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.18), transparent 42%);
  color: rgba(255, 255, 255, 0.96);
  font: inherit;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    inset 0 -10px 18px rgba(4, 11, 24, 0.05);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    transform 180ms ease;
}

.glass-input::placeholder {
  color: rgba(232, 244, 255, 0.58);
}

.glass-input:hover {
  border-color: rgba(255, 255, 255, 0.32);
}

.glass-input:focus {
  outline: none;
  border-color: rgba(124, 215, 228, 0.72);
  box-shadow:
    0 0 0 4px rgba(124, 215, 228, 0.14),
    0 16px 30px rgba(124, 215, 228, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.34);
  transform: translateY(-1px);
}

.password-wrap .glass-input {
  padding-right: 68px;
}

.password-toggle {
  position: absolute;
  top: 50%;
  right: 10px;
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.08)),
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.14), transparent 44%);
  color: rgba(243, 250, 255, 0.84);
  cursor: pointer;
  transform: translateY(-50%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.26),
    inset 0 -1px 0 rgba(255, 255, 255, 0.06);
}

.password-toggle:hover {
  border-color: rgba(124, 215, 228, 0.5);
  color: rgba(255, 255, 255, 0.98);
}

.password-toggle svg {
  width: 18px;
  height: 18px;
}

.form-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.remember-control {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.remember-native {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.remember-box {
  display: grid;
  place-items: center;
  width: 20px;
  height: 20px;
  border-radius: 7px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.1);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
  transition:
    background-color 180ms ease,
    border-color 180ms ease,
    box-shadow 180ms ease;
}

.remember-box svg {
  width: 12px;
  height: 12px;
  color: #04101d;
  opacity: 0;
  transition: opacity 180ms ease;
}

.remember-native:checked + .remember-box {
  border-color: rgba(124, 215, 228, 0.82);
  background: linear-gradient(135deg, var(--accent-cyan), #a7f0d4);
  box-shadow: 0 10px 22px rgba(66, 164, 168, 0.2);
}

.remember-native:checked + .remember-box svg {
  opacity: 1;
}

.remember-text,
.forgot-link,
.modal-footer span,
.modal-footer a {
  font-size: 0.9rem;
}

.remember-text {
  color: rgba(235, 246, 255, 0.78);
}

.forgot-link,
.modal-footer a {
  color: rgba(240, 248, 255, 0.92);
  text-decoration: none;
}

.forgot-link:hover,
.modal-footer a:hover {
  color: #ffffff;
}

.submit-button {
  width: 100%;
  margin-top: 6px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.42),
    inset 0 -1px 0 rgba(255, 255, 255, 0.08),
    0 24px 48px rgba(25, 83, 124, 0.28);
}

.submit-button:disabled {
  opacity: 0.82;
  cursor: not-allowed;
  transform: none;
}

.button-content {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.spin {
  animation: spin 0.9s linear infinite;
}

.modal-footer {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 20px;
  color: rgba(232, 244, 255, 0.72);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

.modal-fade-enter-from .login-modal,
.modal-fade-leave-to .login-modal {
  transform: translateY(10px) scale(0.98);
}

@keyframes drift {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(0, -14px, 0) scale(1.05);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 900px) {
  .landing-stage {
    padding: 20px 18px 28px;
  }

  .landing-header {
    position: relative;
    top: auto;
    left: auto;
    margin-bottom: 26px;
  }

  .hero-content {
    padding-top: 12px;
  }

  .hero-title {
    font-size: clamp(2.7rem, 10vw, 4.2rem);
    max-width: 11em;
  }
}

@media (max-width: 640px) {
  .brand-chip {
    max-width: calc(100vw - 28px);
    padding: 5px 11px 5px 8px;
    border-radius: 24px;
  }

  .brand-mark {
    width: 37px;
    height: 37px;
  }

  .brand-mark svg {
    width: 27px;
    height: 27px;
  }

  .brand-name-en {
    font-size: 0.65rem;
  }

  .brand-name-cn {
    font-size: 0.58rem;
    letter-spacing: 0.04em;
  }

  .hero-eyebrow {
    font-size: 0.74rem;
    line-height: 1.45;
  }

  .hero-title {
    margin-top: 22px;
    max-width: 9.5em;
    font-size: clamp(2.35rem, 10.4vw, 3.45rem);
    line-height: 1.16;
  }

  .hero-subtitle-en {
    margin-top: 20px;
    font-size: clamp(1.06rem, 5vw, 1.3rem);
  }

  .hero-subtitle-cn {
    margin-top: 6px;
    font-size: clamp(0.9rem, 3.8vw, 1rem);
  }

  .primary-cta {
    min-height: 56px;
    min-width: 154px;
    padding: 0 22px;
  }

  .cta-label {
    min-height: 56px;
  }

  .modal-layer {
    padding: 18px;
  }

  .login-modal {
    padding: 26px 18px 20px;
    border-radius: 24px;
  }

  .modal-footer,
  .form-meta {
    flex-wrap: wrap;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ambient,
  .spin {
    animation: none !important;
  }

  .login-video {
    transform: none;
  }
}
</style>
