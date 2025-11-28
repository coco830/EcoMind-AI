<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <h1 class="error-code">404</h1>
    <p class="error-message">页面未找到</p>
    <p class="error-description">抱歉，您访问的页面不存在</p>
    <el-button type="primary" @click="router.push('/')">
      返回首页
    </el-button>
  </div>
</template>

<style scoped>
.not-found {
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}

.error-code {
  font-size: 120px;
  color: #409eff;
  margin: 0;
  font-weight: bold;
}

.error-message {
  font-size: 24px;
  color: #333;
  margin: 20px 0 10px;
}

.error-description {
  color: #999;
  margin-bottom: 30px;
}
</style>
