<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { authApi } from '@/api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const verifying = ref(true)
const tokenValid = ref(false)
const tokenError = ref('')
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const resetSuccess = ref(false)

const form = reactive({
  password: '',
  confirmPassword: ''
})

// Nature background image (same as login)
const backgroundImage = "https://images.unsplash.com/photo-1437482078695-73f5ca6c96e2?ixlib=rb-4.0.3&auto=format&fit=crop&w=1600&q=80"

const token = ref('')

onMounted(async () => {
  token.value = route.query.token as string || ''

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
  } catch (error) {
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
    ElMessage.warning('密码长度至少8个字符')
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
    ElMessage.success('密码重置成功')
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
  <div class="flex min-h-screen bg-white font-sans selection:bg-eco-blue selection:text-white">
    <!-- Left Section: Image & Branding -->
    <div class="hidden lg:block lg:w-1/2 relative overflow-hidden">
      <!-- Background Image - Nature Theme -->
      <div class="absolute inset-0">
        <img
          :src="backgroundImage"
          alt="Nature landscape with river and forest"
          class="object-cover w-full h-full"
        />
        <!-- Deep Blue Overlay -->
        <div class="absolute inset-0 bg-[#0B1727]/20"></div>
      </div>

      <!-- Brand Overlay - Logo & Text -->
      <div class="absolute top-16 left-16 flex items-center gap-3 z-10">
        <div class="text-white drop-shadow-xl">
          <svg
            viewBox="0 0 89 95"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            class="w-16 h-16"
          >
            <g fill="currentColor">
              <path d="M51 14 L44 23 L38 34 L40 35 L49 20 L51 19 L55 23 L66 40 L70 50 L70 59 L67 65 L62 70 L56 73 L47 73 L46 75 L56 75 L63 72 L70 65 L72 60 L71 46 L66 36 Z" />
              <path d="M16 32 L15 33 L15 48 L18 55 L25 62 L35 65 L39 70 L38 64 L35 57 L31 51 L23 43 L25 42 L31 46 L38 53 L43 61 L44 59 L44 48 L43 46 L35 38 Z" />
              <path d="M65 53 L63 53 L61 60 L54 66 L55 67 L59 66 L62 63 L65 58 Z" />
            </g>
          </svg>
        </div>
        <span class="text-white text-4xl font-semibold tracking-wide drop-shadow-xl">
          YueenEcoMind-AI
        </span>
      </div>

      <!-- Quote / Tagline at bottom left -->
      <div class="absolute bottom-16 left-16 right-16 z-10">
        <p class="text-2xl font-light tracking-wide leading-relaxed text-white drop-shadow-lg">
          Empowering a greener future through intelligence.
        </p>
        <p class="text-lg font-light mt-1 tracking-wider text-white drop-shadow-lg">
          通过智慧力量推动更绿色的未来
        </p>
      </div>
    </div>

    <!-- Right Section: Reset Password Form -->
    <div class="w-full lg:w-1/2 flex flex-col justify-center items-center px-8 md:px-16 xl:px-32 relative bg-white">

      <!-- Mobile Header -->
      <div class="lg:hidden absolute top-8 left-8 flex items-center gap-3 mb-8">
        <div class="text-eco-blue">
          <svg viewBox="0 0 89 95" fill="none" xmlns="http://www.w3.org/2000/svg" class="w-10 h-10">
            <g fill="currentColor">
              <path d="M51 14 L44 23 L38 34 L40 35 L49 20 L51 19 L55 23 L66 40 L70 50 L70 59 L67 65 L62 70 L56 73 L47 73 L46 75 L56 75 L63 72 L70 65 L72 60 L71 46 L66 36 Z" />
              <path d="M16 32 L15 33 L15 48 L18 55 L25 62 L35 65 L39 70 L38 64 L35 57 L31 51 L23 43 L25 42 L31 46 L38 53 L43 61 L44 59 L44 48 L43 46 L35 38 Z" />
              <path d="M65 53 L63 53 L61 60 L54 66 L55 67 L59 66 L62 63 L65 58 Z" />
            </g>
          </svg>
        </div>
        <span class="text-eco-blue text-2xl font-bold">YueenEcoMind-AI</span>
      </div>

      <div class="w-full max-w-[440px] space-y-12">

        <!-- Header Text Section -->
        <div class="space-y-3 text-left">
          <h1 class="text-5xl text-gray-900 font-bold tracking-normal">
            Reset Password
          </h1>
          <p class="text-gray-400 text-sm tracking-normal font-medium">
            重置密码
          </p>
        </div>

        <!-- Loading State -->
        <div v-if="verifying" class="flex flex-col items-center justify-center py-12">
          <svg class="animate-spin h-10 w-10 text-eco-blue mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <p class="text-gray-500">验证链接中...</p>
        </div>

        <!-- Invalid Token State -->
        <div v-else-if="!tokenValid && !resetSuccess" class="space-y-8">
          <div class="bg-red-50 border border-red-200 rounded-2xl p-6 text-center">
            <svg class="w-16 h-16 mx-auto text-red-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h3 class="text-lg font-semibold text-gray-900 mb-2">链接无效</h3>
            <p class="text-gray-600 text-sm">{{ tokenError }}</p>
            <p class="text-gray-400 text-xs mt-4">
              重置链接可能已过期或已被使用。
            </p>
          </div>

          <button
            @click="goToForgotPassword"
            class="w-full py-4 px-6 rounded-full font-medium tracking-wide transition-all duration-300 bg-[#0B1727] text-white shadow-[0_8px_20px_rgba(11,23,39,0.25)] hover:shadow-[0_12px_28px_rgba(11,23,39,0.35)] hover:-translate-y-0.5"
          >
            重新申请重置链接
          </button>

          <div class="text-center">
            <a
              @click.prevent="goToLogin"
              href="#"
              class="text-gray-400 text-sm hover:text-eco-blue transition-colors cursor-pointer"
            >
              <span class="mr-1">&larr;</span> 返回登录
            </a>
          </div>
        </div>

        <!-- Success State -->
        <div v-else-if="resetSuccess" class="space-y-8">
          <div class="bg-green-50 border border-green-200 rounded-2xl p-6 text-center">
            <svg class="w-16 h-16 mx-auto text-green-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 class="text-lg font-semibold text-gray-900 mb-2">密码重置成功</h3>
            <p class="text-gray-600 text-sm">
              您的密码已成功重置，请使用新密码登录。
            </p>
          </div>

          <button
            @click="goToLogin"
            class="w-full py-4 px-6 rounded-full font-medium tracking-wide transition-all duration-300 bg-[#0B1727] text-white shadow-[0_8px_20px_rgba(11,23,39,0.25)] hover:shadow-[0_12px_28px_rgba(11,23,39,0.35)] hover:-translate-y-0.5"
          >
            前往登录
          </button>
        </div>

        <!-- Form State -->
        <form v-else @submit.prevent="handleSubmit" class="space-y-8">
          <div class="space-y-6">
            <p class="text-gray-500 text-sm">
              请设置您的新密码，密码长度至少8个字符。
            </p>

            <!-- New Password Input -->
            <div class="relative">
              <input
                v-model="form.password"
                name="password"
                :type="showPassword ? 'text' : 'password'"
                placeholder="New Password 新密码"
                required
                class="w-full px-6 py-4 pr-12 bg-white border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 shadow-[0_4px_16px_rgba(0,0,0,0.06)] focus:outline-none focus:bg-white focus:ring-0 focus:shadow-[0_8px_24px_rgba(11,23,39,0.12)] focus:border-[#0B1727]/30 hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] transition-all duration-300 ease-out text-base"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors duration-200 focus:outline-none"
              >
                <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              </button>
            </div>

            <!-- Confirm Password Input -->
            <div class="relative">
              <input
                v-model="form.confirmPassword"
                name="confirmPassword"
                :type="showConfirmPassword ? 'text' : 'password'"
                placeholder="Confirm Password 确认密码"
                required
                class="w-full px-6 py-4 pr-12 bg-white border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 shadow-[0_4px_16px_rgba(0,0,0,0.06)] focus:outline-none focus:bg-white focus:ring-0 focus:shadow-[0_8px_24px_rgba(11,23,39,0.12)] focus:border-[#0B1727]/30 hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] transition-all duration-300 ease-out text-base"
              />
              <button
                type="button"
                @click="showConfirmPassword = !showConfirmPassword"
                class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors duration-200 focus:outline-none"
              >
                <svg v-if="!showConfirmPassword" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
                <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                </svg>
              </button>
            </div>

            <!-- Password Requirements -->
            <div class="text-xs text-gray-400 space-y-1 px-2">
              <p :class="form.password.length >= 8 ? 'text-green-500' : ''">
                <span v-if="form.password.length >= 8">&#10003;</span>
                <span v-else>&#8226;</span>
                至少8个字符
              </p>
              <p :class="form.password && form.confirmPassword && form.password === form.confirmPassword ? 'text-green-500' : ''">
                <span v-if="form.password && form.confirmPassword && form.password === form.confirmPassword">&#10003;</span>
                <span v-else>&#8226;</span>
                两次密码一致
              </p>
            </div>
          </div>

          <!-- Submit Button -->
          <div class="pt-2">
            <button
              type="submit"
              :disabled="loading || form.password.length < 8 || form.password !== form.confirmPassword"
              class="w-full py-4 px-6 rounded-full font-medium tracking-wide transition-all duration-300 bg-[#0B1727] text-white shadow-[0_8px_20px_rgba(11,23,39,0.25)] hover:shadow-[0_12px_28px_rgba(11,23,39,0.35)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_4px_10px_rgba(11,23,39,0.2)] disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none"
            >
              <span v-if="loading" class="flex items-center justify-center gap-2">
                <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                重置中...
              </span>
              <span v-else>Reset Password 重置密码</span>
            </button>
          </div>

          <!-- Back to Login -->
          <div class="text-center">
            <a
              @click.prevent="goToLogin"
              href="#"
              class="text-gray-400 text-sm hover:text-eco-blue transition-colors cursor-pointer"
            >
              <span class="mr-1">&larr;</span> 返回登录
            </a>
          </div>
        </form>

      </div>
    </div>
  </div>
</template>

<style scoped>
.text-eco-blue {
  color: #1E6F9F;
}

.bg-eco-blue {
  background-color: #1E6F9F;
}

.hover\:text-eco-blue:hover {
  color: #1E6F9F;
}

.selection\:bg-eco-blue::selection {
  background-color: #1E6F9F;
}
</style>
