# 用户注册功能说明

## 概述

前端已添加完整的用户注册功能，用户可以通过 Web 界面自助注册账号。

## 功能特点

### 1. 注册页面

- **URL**: http://localhost:3000/register
- **功能**:
  - 用户名输入（3-64个字符，仅限字母、数字、下划线）
  - 邮箱地址输入（有效的邮箱格式）
  - 真实姓名输入（可选）
  - 密码输入（至少8个字符）
  - 确认密码（必须与密码一致）
  - 表单验证（实时验证）
  - 错误提示（友好的错误信息）

### 2. 自动分配组织

- 新注册用户自动分配到默认组织（code='DEFAULT'）
- 用户角色默认为 `viewer`（查看者）
- 注册成功后提示用户登录

### 3. 登录页面入口

- **URL**: http://localhost:3000/login
- 在登录页面底部添加了"立即注册"链接
- 点击后跳转到注册页面

### 4. 注册页面返回

- 在注册页面底部提供"立即登录"链接
- 注册成功后自动跳转到登录页面

## 使用流程

### 新用户注册流程

1. 访问登录页面: http://localhost:3000/login
2. 点击底部"立即注册"链接
3. 填写注册信息：
   - 用户名（必填）
   - 邮箱（必填）
   - 真实姓名（可选）
   - 密码（必填，至少8个字符）
   - 确认密码（必填）
4. 点击"注册"按钮
5. 注册成功后自动跳转到登录页面
6. 使用新注册的账号登录

### 验证步骤

#### 方法1: 手动测试（推荐）

1. 打开浏览器访问: http://localhost:3000/login
2. 点击"立即注册"
3. 填写表单信息
4. 提交注册
5. 使用新账号登录

#### 方法2: 使用测试脚本

```bash
cd backend
.venv/bin/python scripts/test_register_frontend.py
```

## 表单验证规则

| 字段 | 规则 |
|------|------|
| 用户名 | 必填，3-64字符，仅限字母、数字、下划线 |
| 邮箱 | 必填，有效的邮箱格式 |
| 真实姓名 | 可选，最多128字符 |
| 密码 | 必填，8-128字符 |
| 确认密码 | 必填，必须与密码一致 |

## 错误处理

### 常见错误提示

1. **用户名已存在**
   ```
   Username already registered
   ```

2. **邮箱已注册**
   ```
   Email already registered
   ```

3. **密码不一致**
   ```
   两次输入的密码不一致
   ```

4. **验证错误**
   - 用户名格式错误
   - 邮箱格式无效
   - 密码长度不足

## 技术实现

### 前端组件

- **文件**: `frontend/src/views/Register.vue`
- **框架**: Vue 3 + Composition API
- **UI组件**: Element Plus
- **表单验证**: Element Plus Form Validation

### API 接口

- **端点**: `POST /api/v1/auth/register`
- **请求体**:
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string",
    "full_name": "string (optional)"
  }
  ```
- **响应**:
  ```json
  {
    "id": "uuid",
    "username": "string",
    "email": "string",
    "full_name": "string",
    "role": "viewer",
    "is_active": true,
    "is_superadmin": false,
    "org_id": "uuid",
    "created_at": "datetime",
    "updated_at": "datetime"
  }
  ```

### 路由配置

```typescript
{
  path: '/register',
  name: 'Register',
  component: () => import('@/views/Register.vue'),
  meta: { requiresAuth: false }
}
```

## 页面截图指南

访问以下页面进行测试：

1. **登录页面**: http://localhost:3000/login
   - 可以看到"立即注册"链接

2. **注册页面**: http://localhost:3000/register
   - 完整的注册表单
   - 表单验证提示
   - "立即登录"链接

## 安全特性

1. **密码强度要求**: 至少8个字符
2. **邮箱验证**: 确保邮箱格式正确
3. **用户名唯一性**: 防止重复注册
4. **邮箱唯一性**: 一个邮箱只能注册一个账号
5. **前端验证**: 实时表单验证
6. **后端验证**: API层面的数据验证

## 默认权限

新注册用户的默认设置：

- **角色**: viewer（查看者）
- **状态**: is_active = true（激活）
- **超级管理员**: is_superadmin = false
- **组织**: 自动分配到默认组织

## 后续改进建议

1. 添加邮箱验证功能（发送验证邮件）
2. 添加图形验证码
3. 添加密码强度指示器
4. 添加用户协议和隐私政策勾选
5. 支持第三方登录（微信、QQ等）
6. 添加注册成功欢迎页面

## 测试数据

可以使用以下测试数据进行注册：

```
用户名: testuser001
邮箱: testuser001@example.com
姓名: 测试用户
密码: password123
```

## 相关文档

- [多租户功能文档](./MULTI_TENANCY.md)
- [验收指南](./ACCEPTANCE_GUIDE.md)
- [API文档](http://localhost:8000/docs)

---

**更新日期**: 2025-11-27
**功能状态**: ✅ 已完成并测试通过
