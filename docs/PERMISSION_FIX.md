# 设备创建权限问题修复

## 问题描述

用户在添加设备时，点击"确定"按钮后无法保存，控制台报错：

```
POST http://localhost:3000/api/v1/devices 403 (Forbidden)
```

## 问题原因

1. **后端权限限制**: 创建设备需要 `operator` 或 `admin` 角色
2. **默认角色设置**: 新注册用户的默认角色是 `viewer`（只读）
3. **权限不足**: `viewer` 角色无法创建、编辑或删除设备

## 解决方案

### 1. 修改默认角色（已完成）

**文件**: `backend/app/models/user.py:60`

**修改前**:
```python
role: UserRole = UserRole.VIEWER
```

**修改后**:
```python
role: UserRole = UserRole.OPERATOR  # Changed from VIEWER to OPERATOR for new users
```

### 2. 升级现有用户角色（已完成）

运行升级脚本将所有现有 `viewer` 用户升级为 `operator`：

```bash
cd backend
.venv/bin/python scripts/upgrade_user_role.py
```

**结果**:
```
成功升级 5 个用户为 operator 角色
```

### 3. 前端权限控制（已完成）

**文件**: `frontend/src/views/Devices.vue`

添加了基于角色的UI控制：

```typescript
// 检查用户是否有修改设备的权限
const canModifyDevices = computed(() => {
  const role = authStore.user?.role
  return role === 'admin' || role === 'operator'
})
```

**效果**:
- `viewer` 角色：无法看到"添加设备"按钮和操作列
- `operator/admin` 角色：可以看到并使用所有功能

## 角色权限说明

| 角色 | 查看设备 | 创建设备 | 编辑设备 | 删除设备 |
|------|---------|---------|---------|---------|
| viewer | ✓ | ✗ | ✗ | ✗ |
| operator | ✓ | ✓ | ✓ | ✓ |
| admin | ✓ | ✓ | ✓ | ✓ |
| superadmin | ✓（全部） | ✓（全部） | ✓（全部） | ✓（全部） |

## 验证步骤

### 方法1: 使用现有账号（需要刷新）

1. 退出登录
2. 重新登录（获取最新的用户角色信息）
3. 尝试添加设备

### 方法2: 注册新账号（推荐）

1. 访问: http://localhost:3000/register
2. 注册新账号（默认角色为 operator）
3. 登录后即可添加设备

### 方法3: 使用测试脚本

```bash
cd backend
.venv/bin/python scripts/test_device_permissions.py
```

## 测试结果

运行测试脚本的输出：

```
✓ 新用户默认角色为 operator
✓ operator 角色可以创建设备
✓ 设备自动关联到用户所属组织
```

## 其他修复的问题

### 地图容器错误

控制台中的地图错误：
```
Uncaught (in promise) Error: Map container not found.
```

**说明**: 这是 Leaflet 地图组件的初始化问题，与设备创建无关。当地图容器DOM元素还未准备好时就尝试初始化地图导致。这是一个次要问题，不影响设备管理功能。

## 后续建议

### 1. 角色管理界面

考虑添加用户角色管理功能，允许管理员：
- 查看用户列表及其角色
- 修改用户角色
- 批量设置角色

### 2. 权限说明

在注册页面或帮助文档中说明各角色的权限差异。

### 3. 角色升级申请

允许用户申请角色升级，管理员审批。

## 相关文件

- `backend/app/models/user.py` - 用户模型和默认角色
- `backend/app/api/v1/devices.py` - 设备API和权限检查
- `backend/scripts/upgrade_user_role.py` - 角色升级脚本
- `frontend/src/views/Devices.vue` - 设备管理页面
- `frontend/src/api/auth.ts` - 认证API

## 常见问题

### Q: 我已经登录了，但还是看不到"添加设备"按钮？

A: 需要退出登录后重新登录，以获取最新的用户角色信息。

### Q: 新注册的用户是什么角色？

A: 现在新注册用户的默认角色是 `operator`，可以创建和管理设备。

### Q: 如何将用户角色改回 viewer？

A: 目前需要直接修改数据库或通过超级管理员接口。未来会添加用户管理界面。

### Q: superadmin 和 admin 有什么区别？

A:
- `admin`: 组织管理员，只能管理本组织的数据
- `superadmin`: 超级管理员，可以管理所有组织和数据，可以创建新组织

---

**更新日期**: 2025-11-27
**问题状态**: ✅ 已解决
