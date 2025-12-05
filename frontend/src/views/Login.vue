<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const showPassword = ref(false)
const rememberMe = ref(false)

const form = reactive({
  username: '',
  password: ''
})

// Load saved credentials on mount
onMounted(() => {
  const savedUsername = localStorage.getItem('ecomind_username')
  const savedPassword = localStorage.getItem('ecomind_password')
  const savedRemember = localStorage.getItem('ecomind_remember')

  if (savedRemember === 'true' && savedUsername) {
    form.username = savedUsername
    form.password = savedPassword || ''
    rememberMe.value = true
  }
})

// Nature background image
const backgroundImage = "https://images.unsplash.com/photo-1437482078695-73f5ca6c96e2?ixlib=rb-4.0.3&auto=format&fit=crop&w=1600&q=80"

const handleLogin = async () => {
  // Basic validation
  if (!form.username.trim()) {
    ElMessage.warning('请输入用户名')
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

    // Save or clear credentials based on remember me
    if (rememberMe.value) {
      localStorage.setItem('ecomind_username', form.username.trim())
      localStorage.setItem('ecomind_password', form.password)
      localStorage.setItem('ecomind_remember', 'true')
    } else {
      localStorage.removeItem('ecomind_username')
      localStorage.removeItem('ecomind_password')
      localStorage.removeItem('ecomind_remember')
    }

    ElMessage.success('登录成功')

    const redirect = route.query.redirect as string
    router.push(redirect || '/')
  } catch (error) {
    ElMessage.error('登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}

const goToRegister = () => {
  router.push({ name: 'Register' })
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
          <!-- Logo SVG -->
          <svg
            viewBox="0 0 89 95"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            class="w-16 h-16"
          >
            <g fill="currentColor">
              <!-- Water drop outline -->
              <path d="M51 14 L44 23 L38 34 L40 35 L49 20 L51 19 L55 23 L66 40 L70 50 L70 59 L67 65 L62 70 L56 73 L47 73 L46 75 L56 75 L63 72 L70 65 L72 60 L71 46 L66 36 Z" />
              <!-- Leaf -->
              <path d="M16 32 L15 33 L15 48 L18 55 L25 62 L35 65 L39 70 L38 64 L35 57 L31 51 L23 43 L25 42 L31 46 L38 53 L43 61 L44 59 L44 48 L43 46 L35 38 Z" />
              <!-- Inner arc -->
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

    <!-- Right Section: Login Form -->
    <div class="w-full lg:w-1/2 flex flex-col justify-center items-center px-8 md:px-16 xl:px-32 relative bg-white">

      <!-- Mobile Header (Only visible on small screens) -->
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
            Welcome Back
          </h1>
          <p class="text-gray-400 text-sm tracking-normal font-medium">
            YueenEcoMind-AI 智慧环保中台
          </p>
        </div>

        <!-- Form -->
        <form @submit.prevent="handleLogin" class="space-y-8">
          <div class="space-y-6">
            <!-- Username Input -->
            <input
              v-model="form.username"
              name="username"
              type="text"
              placeholder="Username 用户名"
              required
              class="w-full px-6 py-4 bg-white border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 shadow-[0_4px_16px_rgba(0,0,0,0.06)] focus:outline-none focus:bg-white focus:ring-0 focus:shadow-[0_8px_24px_rgba(11,23,39,0.12)] focus:border-[#0B1727]/30 hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] transition-all duration-300 ease-out text-base"
            />

            <!-- Password Input -->
            <div class="space-y-2">
              <div class="relative">
                <input
                  v-model="form.password"
                  name="password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="Password 密码"
                  required
                  @keyup.enter="handleLogin"
                  class="w-full px-6 py-4 pr-12 bg-white border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 shadow-[0_4px_16px_rgba(0,0,0,0.06)] focus:outline-none focus:bg-white focus:ring-0 focus:shadow-[0_8px_24px_rgba(11,23,39,0.12)] focus:border-[#0B1727]/30 hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] transition-all duration-300 ease-out text-base"
                />
                <!-- Password Visibility Toggle -->
                <button
                  type="button"
                  @click="showPassword = !showPassword"
                  class="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors duration-200 focus:outline-none"
                >
                  <!-- Eye Open Icon -->
                  <svg v-if="!showPassword" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                  <!-- Eye Closed Icon -->
                  <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                </button>
              </div>
              <!-- Remember Me & Forgot Password -->
              <div class="flex items-center justify-between pt-2 px-6">
                <label class="flex items-center gap-2.5 cursor-pointer group">
                  <div class="relative">
                    <input
                      v-model="rememberMe"
                      type="checkbox"
                      class="peer sr-only"
                    />
                    <div class="w-4 h-4 bg-white border border-gray-200 rounded-md shadow-[0_4px_16px_rgba(0,0,0,0.06)] peer-checked:bg-eco-blue peer-checked:border-eco-blue peer-focus:shadow-[0_8px_24px_rgba(11,23,39,0.12)] hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] transition-all duration-300 cursor-pointer"></div>
                    <svg class="absolute top-0.5 left-0.5 w-3 h-3 text-white opacity-0 peer-checked:opacity-100 transition-opacity duration-200 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <span class="text-gray-400 text-xs tracking-wide font-medium group-hover:text-gray-500 transition-colors duration-200">记住密码</span>
                </label>
                <a
                  @click.prevent="goToForgotPassword"
                  href="#"
                  class="text-gray-400 text-xs tracking-wide font-medium hover:text-eco-blue transition-colors duration-200 cursor-pointer"
                >
                  忘记密码？
                </a>
              </div>
            </div>
          </div>

          <!-- Submit Button -->
          <div class="pt-2">
            <button
              type="submit"
              :disabled="loading"
              class="w-full py-4 px-6 rounded-full font-medium tracking-wide transition-all duration-300 bg-[#0B1727] text-white shadow-[0_8px_20px_rgba(11,23,39,0.25)] hover:shadow-[0_12px_28px_rgba(11,23,39,0.35)] hover:-translate-y-0.5 active:translate-y-0 active:shadow-[0_4px_10px_rgba(11,23,39,0.2)] disabled:opacity-70 disabled:cursor-not-allowed disabled:transform-none"
            >
              <span v-if="loading" class="flex items-center justify-center gap-2">
                <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                登录中...
              </span>
              <span v-else>Login 登录</span>
            </button>
          </div>
        </form>

      </div>

      <!-- Footer: Sign Up -->
      <div class="absolute bottom-12 w-full text-center">
        <p class="text-gray-400 text-sm">
          还没有账号？
          <a
            @click.prevent="goToRegister"
            href="#"
            class="text-gray-800 font-semibold hover:text-eco-blue transition-colors ml-1 cursor-pointer"
          >
            立即注册
          </a>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Custom eco-blue color fallback if Tailwind isn't fully loaded */
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
