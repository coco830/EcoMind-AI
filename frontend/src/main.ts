import { createApp } from 'vue'
import { createPinia } from 'pinia'
import 'element-plus/dist/index.css'
import { installElementPlus } from '@/plugins/element-plus'
import { registerElementPlusIcons } from '@/plugins/element-plus-icons'

// Global styles - Apple-inspired design system
import './styles/global.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)

app.use(createPinia())
app.use(router)
installElementPlus(app)
registerElementPlusIcons(app)

app.mount('#app')
