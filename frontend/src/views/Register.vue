<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { apiBasePath } from '@/api/request'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const showPassword = ref(false)
const showConfirmPassword = ref(false)

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

// 邀请码验证状态
const invitationValid = ref(false)
const invitationName = ref('')
const checkingCode = ref(false)

// 验证邀请码
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
    errors.invitation_code = '验证邀请码失败'
  } finally {
    checkingCode.value = false
  }
}

const validateForm = (): boolean => {
  let isValid = true

  // Reset errors
  errors.username = ''
  errors.email = ''
  errors.password = ''
  errors.confirmPassword = ''
  errors.full_name = ''
  errors.invitation_code = ''

  // Invitation code validation
  if (!form.invitation_code.trim()) {
    errors.invitation_code = '请输入邀请码'
    isValid = false
  } else if (!invitationValid.value) {
    errors.invitation_code = '请先验证邀请码'
    isValid = false
  }

  // Username validation
  if (!form.username.trim()) {
    errors.username = '请输入用户名'
    isValid = false
  } else if (form.username.length < 3 || form.username.length > 64) {
    errors.username = '用户名长度 3-64 个字符'
    isValid = false
  } else if (!/^[a-zA-Z0-9_]+$/.test(form.username)) {
    errors.username = '仅限字母、数字和下划线'
    isValid = false
  }

  // Email validation
  if (!form.email.trim()) {
    errors.email = '请输入邮箱'
    isValid = false
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = '请输入有效的邮箱地址'
    isValid = false
  }

  // Password validation
  if (!form.password) {
    errors.password = '请输入密码'
    isValid = false
  } else if (form.password.length < 8) {
    errors.password = '密码至少8个字符'
    isValid = false
  }

  // Confirm password validation
  if (!form.confirmPassword) {
    errors.confirmPassword = '请确认密码'
    isValid = false
  } else if (form.confirmPassword !== form.password) {
    errors.confirmPassword = '两次密码不一致'
    isValid = false
  }

  // Full name validation (optional)
  if (form.full_name && form.full_name.length > 128) {
    errors.full_name = '姓名不能超过128个字符'
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

    ElMessage.success('注册成功！请登录')
    router.push({ name: 'Login' })
  } catch (error: any) {
    const message = error?.response?.data?.detail || '注册失败，请重试'
    if (typeof message === 'string') {
      ElMessage.error(message)
    } else if (Array.isArray(message)) {
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
  <div class="min-h-screen bg-[#F5F5F7] flex items-center justify-center p-6 font-sans">
    <!-- Subtle background pattern -->
    <div class="fixed inset-0 opacity-[0.015] bg-pattern"></div>

    <!-- Main Bento Container -->
    <div class="relative w-full max-w-[520px]">

      <!-- Floating Card -->
      <div class="relative bg-white/80 backdrop-blur-2xl rounded-[32px] shadow-[0_12px_48px_rgba(0,0,0,0.08),0_4px_16px_rgba(0,0,0,0.04),0_1px_4px_rgba(0,0,0,0.02)] border border-black/[0.04] overflow-hidden">

        <!-- Top accent line -->
        <div class="absolute top-0 left-1/2 -translate-x-1/2 w-24 h-1 bg-gradient-to-r from-transparent via-black/10 to-transparent rounded-full"></div>

        <!-- Content -->
        <div class="p-10 pt-12">

          <!-- Header -->
          <div class="text-center mb-10">
            <!-- Logo -->
            <div class="inline-flex items-center justify-center w-20 h-20 rounded-[24px] bg-gradient-to-br from-[#F8F9FA] to-[#E9ECEF] shadow-[0_6px_20px_rgba(0,0,0,0.06),0_2px_8px_rgba(0,0,0,0.04),inset_0_1px_1px_rgba(255,255,255,0.8)] mb-5">
              <svg viewBox="0 0 89 95" fill="none" xmlns="http://www.w3.org/2000/svg" class="w-11 h-11 text-[#1D1D1F]">
                <g fill="currentColor">
                  <path d="M51 14 L44 23 L38 34 L40 35 L49 20 L51 19 L55 23 L66 40 L70 50 L70 59 L67 65 L62 70 L56 73 L47 73 L46 75 L56 75 L63 72 L70 65 L72 60 L71 46 L66 36 Z" />
                  <path d="M16 32 L15 33 L15 48 L18 55 L25 62 L35 65 L39 70 L38 64 L35 57 L31 51 L23 43 L25 42 L31 46 L38 53 L43 61 L44 59 L44 48 L43 46 L35 38 Z" />
                  <path d="M65 53 L63 53 L61 60 L54 66 L55 67 L59 66 L62 63 L65 58 Z" />
                </g>
              </svg>
            </div>

            <h1 class="text-[28px] font-semibold text-[#1D1D1F] tracking-tight mb-2">
              创建账户
            </h1>
            <p class="text-[15px] text-[#86868B]">
              加入 YueenEcoMind-AI 智慧环保平台
            </p>
          </div>

          <!-- Form -->
          <form @submit.prevent="handleRegister" class="space-y-5">

            <!-- Invitation Code Field -->
            <div class="space-y-2">
              <label class="block text-[13px] font-medium text-[#1D1D1F] pl-1">
                邀请码 <span class="text-red-400">*</span>
              </label>
              <div class="relative">
                <input
                  v-model="form.invitation_code"
                  type="text"
                  placeholder="请输入邀请码 (如: XXXX-XXXX-XXXX)"
                  @blur="validateInvitationCode"
                  :class="[
                    'w-full h-[52px] px-5 pr-24 rounded-2xl text-[15px] text-[#1D1D1F] placeholder-[#AEAEB2] uppercase',
                    'bg-[#F5F5F7] border-none outline-none',
                    'transition-all duration-300 ease-out',
                    'focus:bg-white focus:shadow-[0_0_0_4px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.06)]',
                    errors.invitation_code ? 'ring-2 ring-red-400/50' : '',
                    invitationValid ? 'ring-2 ring-green-400/50' : ''
                  ]"
                />
                <button
                  type="button"
                  @click="validateInvitationCode"
                  :disabled="checkingCode || !form.invitation_code.trim()"
                  class="absolute right-3 top-1/2 -translate-y-1/2 px-3 py-1.5 text-[12px] font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  :class="invitationValid ? 'bg-green-100 text-green-700' : 'bg-[#E5E5EA] text-[#1D1D1F] hover:bg-[#D1D1D6]'"
                >
                  <span v-if="checkingCode">验证中...</span>
                  <span v-else-if="invitationValid">✓ 已验证</span>
                  <span v-else>验证</span>
                </button>
              </div>
              <div v-if="errors.invitation_code" class="text-red-400 text-xs pl-1">
                {{ errors.invitation_code }}
              </div>
              <div v-else-if="invitationValid && invitationName" class="text-green-600 text-xs pl-1">
                企业: {{ invitationName }}
              </div>
            </div>

            <!-- Username Field -->
            <div class="space-y-2">
              <label class="block text-[13px] font-medium text-[#1D1D1F] pl-1">
                用户名
              </label>
              <div class="relative">
                <input
                  v-model="form.username"
                  type="text"
                  placeholder="3-64个字符，字母、数字、下划线"
                  :class="[
                    'w-full h-[52px] px-5 rounded-2xl text-[15px] text-[#1D1D1F] placeholder-[#AEAEB2]',
                    'bg-[#F5F5F7] border-none outline-none',
                    'transition-all duration-300 ease-out',
                    'focus:bg-white focus:shadow-[0_0_0_4px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.06)]',
                    errors.username ? 'ring-2 ring-red-400/50' : ''
                  ]"
                />
                <span v-if="errors.username" class="absolute right-4 top-1/2 -translate-y-1/2 text-red-400 text-xs">
                  {{ errors.username }}
                </span>
              </div>
            </div>

            <!-- Email Field -->
            <div class="space-y-2">
              <label class="block text-[13px] font-medium text-[#1D1D1F] pl-1">
                邮箱地址
              </label>
              <div class="relative">
                <input
                  v-model="form.email"
                  type="email"
                  placeholder="your@email.com"
                  :class="[
                    'w-full h-[52px] px-5 rounded-2xl text-[15px] text-[#1D1D1F] placeholder-[#AEAEB2]',
                    'bg-[#F5F5F7] border-none outline-none',
                    'transition-all duration-300 ease-out',
                    'focus:bg-white focus:shadow-[0_0_0_4px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.06)]',
                    errors.email ? 'ring-2 ring-red-400/50' : ''
                  ]"
                />
                <span v-if="errors.email" class="absolute right-4 top-1/2 -translate-y-1/2 text-red-400 text-xs">
                  {{ errors.email }}
                </span>
              </div>
            </div>

            <!-- Full Name Field (Optional) -->
            <div class="space-y-2">
              <label class="block text-[13px] font-medium text-[#1D1D1F] pl-1">
                真实姓名 <span class="text-[#AEAEB2] font-normal">（选填）</span>
              </label>
              <input
                v-model="form.full_name"
                type="text"
                placeholder="您的姓名"
                class="w-full h-[52px] px-5 rounded-2xl text-[15px] text-[#1D1D1F] placeholder-[#AEAEB2] bg-[#F5F5F7] border-none outline-none transition-all duration-300 ease-out focus:bg-white focus:shadow-[0_0_0_4px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.06)]"
              />
            </div>

            <!-- Password Field -->
            <div class="space-y-2">
              <label class="block text-[13px] font-medium text-[#1D1D1F] pl-1">
                密码
              </label>
              <div class="relative">
                <input
                  v-model="form.password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="至少8个字符"
                  :class="[
                    'w-full h-[52px] px-5 pr-12 rounded-2xl text-[15px] text-[#1D1D1F] placeholder-[#AEAEB2]',
                    'bg-[#F5F5F7] border-none outline-none',
                    'transition-all duration-300 ease-out',
                    'focus:bg-white focus:shadow-[0_0_0_4px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.06)]',
                    errors.password ? 'ring-2 ring-red-400/50' : ''
                  ]"
                />
                <button
                  type="button"
                  @click="showPassword = !showPassword"
                  class="absolute right-4 top-1/2 -translate-y-1/2 text-[#AEAEB2] hover:text-[#86868B] transition-colors"
                >
                  <svg v-if="!showPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                  <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                </button>
                <span v-if="errors.password" class="absolute right-12 top-1/2 -translate-y-1/2 text-red-400 text-xs">
                  {{ errors.password }}
                </span>
              </div>
            </div>

            <!-- Confirm Password Field -->
            <div class="space-y-2">
              <label class="block text-[13px] font-medium text-[#1D1D1F] pl-1">
                确认密码
              </label>
              <div class="relative">
                <input
                  v-model="form.confirmPassword"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  placeholder="再次输入密码"
                  @keyup.enter="handleRegister"
                  :class="[
                    'w-full h-[52px] px-5 pr-12 rounded-2xl text-[15px] text-[#1D1D1F] placeholder-[#AEAEB2]',
                    'bg-[#F5F5F7] border-none outline-none',
                    'transition-all duration-300 ease-out',
                    'focus:bg-white focus:shadow-[0_0_0_4px_rgba(0,0,0,0.04),0_4px_16px_rgba(0,0,0,0.06)]',
                    errors.confirmPassword ? 'ring-2 ring-red-400/50' : ''
                  ]"
                />
                <button
                  type="button"
                  @click="showConfirmPassword = !showConfirmPassword"
                  class="absolute right-4 top-1/2 -translate-y-1/2 text-[#AEAEB2] hover:text-[#86868B] transition-colors"
                >
                  <svg v-if="!showConfirmPassword" class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                  <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                </button>
                <span v-if="errors.confirmPassword" class="absolute right-12 top-1/2 -translate-y-1/2 text-red-400 text-xs">
                  {{ errors.confirmPassword }}
                </span>
              </div>
            </div>

            <!-- Submit Button -->
            <div class="pt-4">
              <button
                type="submit"
                :disabled="loading"
                class="w-full h-[54px] rounded-2xl font-medium text-[15px] transition-all duration-300 ease-out bg-[#1D1D1F] text-white shadow-[0_4px_14px_rgba(0,0,0,0.15)] hover:shadow-[0_6px_20px_rgba(0,0,0,0.2)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_2px_8px_rgba(0,0,0,0.15)] disabled:opacity-60 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-none"
              >
                <span v-if="loading" class="flex items-center justify-center gap-2">
                  <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  注册中...
                </span>
                <span v-else>创建账户</span>
              </button>
            </div>
          </form>

          <!-- Divider -->
          <div class="flex items-center gap-4 my-8">
            <div class="flex-1 h-px bg-gradient-to-r from-transparent via-black/[0.08] to-transparent"></div>
            <span class="text-[13px] text-[#AEAEB2]">或</span>
            <div class="flex-1 h-px bg-gradient-to-r from-transparent via-black/[0.08] to-transparent"></div>
          </div>

          <!-- Login Link -->
          <div class="text-center">
            <p class="text-[14px] text-[#86868B]">
              已有账户？
              <a
                @click.prevent="goToLogin"
                href="#"
                class="text-[#1D1D1F] font-medium hover:text-[#0066CC] transition-colors cursor-pointer ml-1"
              >
                立即登录
              </a>
            </p>
          </div>

          <!-- Info Badge -->
          <div class="mt-6 flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-[#F5F5F7]">
            <svg class="w-4 h-4 text-[#FF9500]" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
            </svg>
            <span class="text-[12px] text-[#86868B]">需要邀请码才能注册，请联系管理员获取</span>
          </div>

        </div>
      </div>

      <!-- Bottom decoration -->
      <div class="mt-8 text-center">
        <p class="text-[12px] text-[#AEAEB2]">
          YueenEcoMind-AI · 智慧环保 · 绿色未来
        </p>
      </div>

    </div>
  </div>
</template>

<style scoped>
/* Background pattern */
.bg-pattern {
  background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
}

/* Ensure Inter font is applied */
.font-sans {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
}

/* Smooth focus transitions */
input:focus {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Custom scrollbar for the page if needed */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
