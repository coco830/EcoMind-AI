import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig(({ mode }) => {
  // 加载环境变量
  const env = loadEnv(mode, process.cwd())
  const isProd = mode === 'production'

  return {
    // 子路径部署：https://www.yueen.cc/ecomind-ai/
    // CloudBase 静态托管需要使用绝对路径
    base: '/ecomind-ai/',

    plugins: [vue()],

    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },

    // 开发服务器配置（仅开发环境生效）
    server: {
      port: 3000,
      proxy: isProd ? undefined : {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true
        }
      }
    },

    // 构建配置
    build: {
      // 输出目录
      outDir: 'dist',

      // 静态资源目录
      assetsDir: 'assets',

      // 生产环境移除 console 和 debugger
      minify: 'terser',
      terserOptions: {
        compress: {
          drop_console: isProd,
          drop_debugger: isProd
        }
      },

      // 代码分割配置
      rollupOptions: {
        output: {
          // 分包策略
          manualChunks(id) {
            if (id.includes('node_modules/vue') || id.includes('node_modules/vue-router') || id.includes('node_modules/pinia')) {
              return 'vue-vendor'
            }
            if (id.includes('node_modules/@element-plus/icons-vue')) {
              return 'element-plus-icons'
            }
            const elementPlusComponent = id.match(/node_modules[/\\]element-plus[/\\]es[/\\]components[/\\]([^/\\]+)/)
            if (elementPlusComponent) {
              return `element-plus-${elementPlusComponent[1]}`
            }
            if (id.includes('node_modules/element-plus')) {
              return 'element-plus-core'
            }
            if (id.includes('node_modules/zrender')) {
              return 'zrender'
            }
            if (id.includes('node_modules/echarts')) {
              return 'echarts'
            }
            if (id.includes('node_modules/leaflet') || id.includes('node_modules/@vue-leaflet/vue-leaflet')) {
              return 'leaflet'
            }
          },
          // 静态资源文件名
          chunkFileNames: 'assets/js/[name]-[hash].js',
          entryFileNames: 'assets/js/[name]-[hash].js',
          assetFileNames: 'assets/[ext]/[name]-[hash].[ext]'
        }
      },

      // 分块大小警告限制 (500KB)
      chunkSizeWarningLimit: 500,

      // 生成 sourcemap（生产环境关闭）
      sourcemap: !isProd
    },

    // 预览服务器配置
    preview: {
      port: 4173
    }
  }
})
