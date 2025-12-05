<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const loading = ref(false)
const submitted = ref(false)

const form = reactive({
  email: ''
})

// Nature background image (same as login)
const backgroundImage = "https://images.unsplash.com/photo-1437482078695-73f5ca6c96e2?ixlib=rb-4.0.3&auto=format&fit=crop&w=1600&q=80"

const handleSubmit = async () => {
  if (!form.email.trim()) {
    ElMessage.warning('请输入邮箱地址')
    return
  }

  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(form.email)) {
    ElMessage.warning('请输入有效的邮箱地址')
    return
  }

  loading.value = true
  try {
    await authApi.forgotPassword({ email: form.email.trim() })
    submitted.value = true
    ElMessage.success('如果该邮箱已注册，您将收到一封密码重置邮件')
  } catch (error: any) {
    // Still show success for security (don't reveal if email exists)
    submitted.value = true
    ElMessage.success('如果该邮箱已注册，您将收到一封密码重置邮件')
  } finally {
    loading.value = false
  }
}

const goToLogin = () => {
  router.push({ name: 'Login' })
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

    <!-- Right Section: Forgot Password Form -->
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
            Forgot Password
          </h1>
          <p class="text-gray-400 text-sm tracking-normal font-medium">
            忘记密码
          </p>
        </div>

        <!-- Success State -->
        <div v-if="submitted" class="space-y-8">
          <div class="bg-green-50 border border-green-200 rounded-2xl p-6 text-center">
            <svg class="w-16 h-16 mx-auto text-green-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <h3 class="text-lg font-semibold text-gray-900 mb-2">邮件已发送</h3>
            <p class="text-gray-600 text-sm">
              如果 <span class="font-medium">{{ form.email }}</span> 是已注册的邮箱，您将收到一封包含密码重置链接的邮件。
            </p>
            <p class="text-gray-400 text-xs mt-4">
              请检查您的收件箱和垃圾邮件文件夹。链接将在30分钟后失效。
            </p>
          </div>

          <button
            @click="goToLogin"
            class="w-full py-4 px-6 rounded-full font-medium tracking-wide transition-all duration-300 bg-[#0B1727] text-white shadow-[0_8px_20px_rgba(11,23,39,0.25)] hover:shadow-[0_12px_28px_rgba(11,23,39,0.35)] hover:-translate-y-0.5"
          >
            返回登录
          </button>
        </div>

        <!-- Form State -->
        <form v-else @submit.prevent="handleSubmit" class="space-y-8">
          <div class="space-y-4">
            <p class="text-gray-500 text-sm">
              请输入您的注册邮箱，我们将向您发送密码重置链接。
            </p>

            <!-- Email Input -->
            <input
              v-model="form.email"
              name="email"
              type="email"
              placeholder="Email 邮箱"
              required
              class="w-full px-6 py-4 bg-white border border-gray-200 rounded-2xl text-gray-800 placeholder-gray-400 shadow-[0_4px_16px_rgba(0,0,0,0.06)] focus:outline-none focus:bg-white focus:ring-0 focus:shadow-[0_8px_24px_rgba(11,23,39,0.12)] focus:border-[#0B1727]/30 hover:shadow-[0_6px_20px_rgba(0,0,0,0.08)] transition-all duration-300 ease-out text-base"
            />
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
                发送中...
              </span>
              <span v-else>Send Reset Link 发送重置链接</span>
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
