# EcoMind-AI 前端部署指南

## 部署架构

- **前端**: 腾讯云静态托管 (CloudBase)
- **后端**: 腾讯云 CVM 服务器
- **访问地址**: https://www.yueen.cc/ecomind-ai/

---

## 1. 环境配置

### 1.1 CloudBase 环境信息

| 配置项 | 值 |
|--------|-----|
| 环境 ID | `yueen-huanbao-1gqfjr5s41e61180` |
| 区域 | `ap-shanghai` |
| 部署路径 | `/ecomind-ai` |

### 1.2 修改生产环境变量

编辑 `.env.production` 文件：

```bash
# .env.production
VITE_API_BASE_URL=https://api.your-domain.com
```

**注意事项：**
- URL 必须使用 HTTPS 协议
- 不要以 `/` 结尾
- 不能使用 `localhost` 或内网地址

### 1.3 子路径配置（已完成）

由于部署在 `www.yueen.cc/ecomind-ai/` 子路径下，以下配置已完成：

**vite.config.ts:**
```typescript
export default defineConfig({
  base: '/ecomind-ai/',
  // ...
})
```

**router/index.ts:**
```typescript
const router = createRouter({
  history: createWebHistory('/ecomind-ai/'),
  routes
})
```

---

## 2. 构建生产版本

```bash
# 进入前端目录
cd frontend

# 安装依赖（如果尚未安装）
npm install

# 构建生产版本
npm run build
```

构建完成后，`dist/` 目录将包含所有静态文件：

```
dist/
├── index.html          # 入口 HTML
├── vite.svg            # 网站图标
└── assets/
    ├── js/             # JavaScript 文件（已分包优化）
    └── css/            # 样式文件
```

---

## 3. 腾讯云静态托管部署

### 方式一：CloudBase CLI 命令行（推荐）

```bash
# 安装 CloudBase CLI（如未安装）
npm install -g @cloudbase/cli

# 登录（首次使用，会打开浏览器扫码）
tcb login

# 部署到子路径 /ecomind-ai
tcb hosting deploy ./dist /ecomind-ai -e yueen-huanbao-1gqfjr5s41e61180
```

**一键部署脚本：**
```bash
npm run build && tcb hosting deploy ./dist /ecomind-ai -e yueen-huanbao-1gqfjr5s41e61180
```

### 方式二：控制台手动上传

1. 登录 [腾讯云 CloudBase 控制台](https://console.cloud.tencent.com/tcb)
2. 选择环境 `yueen-huanbao-1gqfjr5s41e61180`
3. 进入 **静态网站托管** → **文件管理**
4. 创建目录 `ecomind-ai`（如不存在）
5. 进入 `ecomind-ai` 目录，上传 `dist/` 目录内的所有文件

### 方式三：使用 cloudbaserc.json 配置

`cloudbaserc.json` 已配置好：

```json
{
  "envId": "yueen-huanbao-1gqfjr5s41e61180",
  "framework": {
    "plugins": {
      "client": {
        "inputs": {
          "outputPath": "./dist",
          "cloudPath": "/ecomind-ai"
        }
      }
    }
  }
}
```

运行：
```bash
tcb framework deploy
```

---

## 4. 后端 CORS 配置

**重要：** 后端必须配置 CORS，允许来自前端域名的跨域请求。

在后端 `.env` 或配置文件中添加：

```bash
CORS_ORIGINS=["https://www.yueen.cc"]
```

---

## 5. SPA 路由配置（重要）

由于 Vue 使用 History 模式路由，刷新页面时需要服务器返回 `index.html`。

### CloudBase 静态托管配置

在 CloudBase 控制台 → **静态网站托管** → **设置** → **错误页面配置**：

| 错误码 | 响应页面 |
|--------|----------|
| 404 | `/ecomind-ai/index.html` |

这样当用户访问 `/ecomind-ai/devices` 等路由时，刷新页面不会 404。

---

## 6. 验证部署

部署完成后，检查以下内容：

### 6.1 基本访问
- [ ] 访问 https://www.yueen.cc/ecomind-ai/ 页面加载正常
- [ ] 静态资源（JS/CSS）加载正常（无 404）

### 6.2 路由测试
- [ ] 直接访问 https://www.yueen.cc/ecomind-ai/login 正常
- [ ] 页面内跳转正常
- [ ] 刷新页面不会 404

### 6.3 API 测试
- [ ] 打开浏览器开发者工具 → Network
- [ ] 登录时 API 请求正常（无 CORS 错误）
- [ ] Token 正确存储在 localStorage

---

## 7. 常见问题

### Q: 页面白屏或资源 404
**原因：** 资源路径不正确
**解决：**
1. 确认 `vite.config.ts` 中 `base: '/ecomind-ai/'`
2. 重新执行 `npm run build`
3. 检查 `dist/index.html` 中资源路径是否包含 `/ecomind-ai/`

### Q: 刷新页面 404
**原因：** 未配置 SPA 回退
**解决：** 在 CloudBase 控制台配置 404 错误页面指向 `/ecomind-ai/index.html`

### Q: API 请求失败 (CORS 错误)
**原因：** 后端未配置 CORS
**解决：**
1. 后端 CORS 配置添加 `https://www.yueen.cc`
2. 确认 API URL 使用 HTTPS

### Q: 登录后无法跳转
**原因：** 路由基准路径问题
**解决：** 确认 `router/index.ts` 中 `createWebHistory('/ecomind-ai/')`

### Q: 旧版本缓存问题
**原因：** 浏览器缓存了旧的静态资源
**解决：**
1. 强制刷新（Ctrl+Shift+R）
2. 清除浏览器缓存
3. 资源文件名包含 hash，正常情况会自动更新

---

## 8. 构建优化说明

当前配置已包含以下优化：

| 优化项 | 说明 |
|--------|------|
| 代码分割 | Vue/Element Plus/ECharts/Leaflet 分别打包 |
| Tree Shaking | 自动移除未使用代码 |
| 压缩混淆 | 使用 Terser 压缩，移除 console/debugger |
| 资源哈希 | 静态资源添加哈希，支持长期缓存 |
| Gzip | CloudBase 自动开启 Gzip 压缩 |

---

## 9. 文件清单

| 文件 | 用途 |
|------|------|
| `.env.development` | 开发环境配置 |
| `.env.production` | 生产环境配置（API URL） |
| `vite.config.ts` | Vite 构建配置（含 base 路径） |
| `src/router/index.ts` | 路由配置（含基准路径） |
| `cloudbaserc.json` | CloudBase 部署配置 |
| `dist/` | 构建输出目录 |

---

## 10. 快速部署命令

```bash
# 完整部署流程
cd frontend
npm install
npm run build
tcb hosting deploy ./dist /ecomind-ai -e yueen-huanbao-1gqfjr5s41e61180
```
