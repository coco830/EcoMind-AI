<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { invitationsApi, type InvitationCode, type CreateInvitationRequest } from '@/api/invitations'
import { organizationApi, type JurisdictionOption } from '@/api/organizations'
import { apiKeysApi, type ApiKeyAccessScope, type ApiKeyItem } from '@/api/apiKeys'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus/es/components/message/index'
import { ElMessageBox } from 'element-plus/es/components/message-box/index'
import { Plus, CopyDocument, Delete } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const loading = ref(false)
const invitations = ref<InvitationCode[]>([])
const apiKeysLoading = ref(false)
const apiKeys = ref<ApiKeyItem[]>([])
const apiKeyScopeFilter = ref<'all' | ApiKeyAccessScope>('all')
const apiKeyOrgFilter = ref('')
const apiKeyNameKeyword = ref('')
const apiKeyCurrentPage = ref(1)
const apiKeyPageSize = ref(10)
const apiKeyActionLoadingMap = ref<Record<string, boolean>>({})
const defaultOpenApiPermissions = [
  'get_device_status',
  'get_latest_data',
  'get_active_alarms',
  'acknowledge_alarm',
  'get_ai_prediction',
  'get_ai_report'
]

interface ApiKeyForm {
  name: string
  org_id: string
  access_scope: ApiKeyAccessScope
  rate_limit: number
}

// 创建对话框
interface CreateInvitationForm {
  name: string
  description: string
  max_uses: number
  expires_at: string
  org_type: string
  region_code: string
  region_name: string
  park_code: string
  park_name: string
  industry_type: string
  jurisdiction_level: string
  jurisdiction_codes: string[]
}

const createDialogVisible = ref(false)
const createLoading = ref(false)
const scopeOptions = ref<JurisdictionOption[]>([])
const scopeLoading = ref(false)
const apiKeyDialogVisible = ref(false)
const apiKeyLoading = ref(false)
const apiKeyResult = ref('')
const apiKeyTargetOrgName = ref('')
const apiKeyForm = ref<ApiKeyForm>({
  name: '',
  org_id: '',
  access_scope: 'single_org',
  rate_limit: 60
})
const createForm = ref<CreateInvitationForm>({
  name: '',
  description: '',
  max_uses: 1,
  expires_at: '',
  org_type: 'enterprise',
  region_code: '',
  region_name: '',
  park_code: '',
  park_name: '',
  industry_type: '',
  jurisdiction_level: '',
  jurisdiction_codes: []
})

// 检查是否是超级管理员
const isSuperAdmin = computed(() => authStore.user?.is_superadmin === true)
const orgOptions = computed(() => {
  const uniqueMap = new Map<string, string>()
  invitations.value.forEach(item => {
    if (!item.org_id) {
      return
    }
    if (!uniqueMap.has(item.org_id)) {
      uniqueMap.set(item.org_id, item.org_name || item.name)
    }
  })
  return Array.from(uniqueMap.entries()).map(([id, name]) => ({ id, name }))
})
const filteredApiKeys = computed(() => {
  const keyword = apiKeyNameKeyword.value.trim().toLowerCase()
  return apiKeys.value.filter(item => {
    if (apiKeyScopeFilter.value !== 'all' && item.access_scope !== apiKeyScopeFilter.value) {
      return false
    }
    if (apiKeyOrgFilter.value && item.org_id !== apiKeyOrgFilter.value) {
      return false
    }
    if (keyword && !item.name.toLowerCase().includes(keyword)) {
      return false
    }
    return true
  })
})
const pagedApiKeys = computed(() => {
  const start = (apiKeyCurrentPage.value - 1) * apiKeyPageSize.value
  return filteredApiKeys.value.slice(start, start + apiKeyPageSize.value)
})

const setApiKeyActionLoading = (keyId: string, loadingValue: boolean) => {
  apiKeyActionLoadingMap.value = {
    ...apiKeyActionLoadingMap.value,
    [keyId]: loadingValue
  }
}

const isApiKeyActionLoading = (keyId: string) => {
  return apiKeyActionLoadingMap.value[keyId] === true
}

watch([apiKeyScopeFilter, apiKeyOrgFilter, apiKeyNameKeyword, apiKeyPageSize], () => {
  apiKeyCurrentPage.value = 1
})

watch(filteredApiKeys, keys => {
  const maxPage = Math.max(1, Math.ceil(keys.length / apiKeyPageSize.value))
  if (apiKeyCurrentPage.value > maxPage) {
    apiKeyCurrentPage.value = maxPage
  }
})

// 加载邀请码列表
const loadInvitations = async () => {
  loading.value = true
  try {
    invitations.value = await invitationsApi.getAll()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载邀请码失败')
  } finally {
    loading.value = false
  }
}

const loadApiKeys = async () => {
  apiKeysLoading.value = true
  try {
    apiKeys.value = await apiKeysApi.list({ limit: 200 })
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载 API Key 列表失败')
  } finally {
    apiKeysLoading.value = false
  }
}

// 打开创建对话框
const openCreateDialog = () => {
  createForm.value = {
    name: '',
    description: '',
    max_uses: 1,
    expires_at: '',
    org_type: 'enterprise',
    region_code: '',
    region_name: '',
    park_code: '',
    park_name: '',
    industry_type: '',
    jurisdiction_level: '',
    jurisdiction_codes: []
  }
  scopeOptions.value = []
  scopeLoading.value = false
  createDialogVisible.value = true
}

const resetApiKeyForm = () => {
  apiKeyResult.value = ''
  apiKeyTargetOrgName.value = ''
  apiKeyForm.value = {
    name: '',
    org_id: '',
    access_scope: 'single_org',
    rate_limit: 60
  }
}

const getOrgNameById = (orgId: string) => {
  const target = orgOptions.value.find(item => item.id === orgId)
  return target?.name || ''
}

const parsePermissions = (permissions: string | null) => {
  if (!permissions) {
    return []
  }
  try {
    const parsed = JSON.parse(permissions)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const formatPermissions = (permissions: string | null) => {
  if (!permissions) {
    return '全部工具'
  }
  const parsed = parsePermissions(permissions)
  if (parsed.length === 0) {
    return '全部工具'
  }
  return `${parsed.length} 个工具`
}

const maskApiKey = (apiKey: string) => {
  if (!apiKey || apiKey.length < 16) {
    return apiKey
  }
  return `${apiKey.slice(0, 12)}...${apiKey.slice(-6)}`
}

const getApiKeyScopeLabel = (scope: ApiKeyAccessScope) => {
  return scope === 'all_orgs' ? '全企业' : '单企业'
}

const getApiKeyScopeType = (scope: ApiKeyAccessScope) => {
  return scope === 'all_orgs' ? 'warning' : 'success'
}

const getApiKeyStatusType = (isActive: boolean) => {
  return isActive ? 'success' : 'info'
}

const getApiKeyStatusText = (isActive: boolean) => {
  return isActive ? '启用中' : '已禁用'
}

const copyApiKey = async (apiKey: string) => {
  try {
    await navigator.clipboard.writeText(apiKey)
    ElMessage.success('API Key 已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

const toggleApiKeyStatus = async (item: ApiKeyItem) => {
  setApiKeyActionLoading(item.id, true)
  try {
    await apiKeysApi.toggle(item.id)
    ElMessage.success(item.is_active ? 'API Key 已禁用' : 'API Key 已启用')
    await loadApiKeys()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '更新 API Key 状态失败')
  } finally {
    setApiKeyActionLoading(item.id, false)
  }
}

const revokeApiKey = async (item: ApiKeyItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要吊销 API Key「${item.name}」吗？吊销后将无法继续调用 OpenAPI 接口。`,
      '吊销确认',
      {
        confirmButtonText: '确认吊销',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
  } catch {
    return
  }

  setApiKeyActionLoading(item.id, true)
  try {
    await apiKeysApi.revoke(item.id)
    ElMessage.success('API Key 已吊销')
    await loadApiKeys()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '吊销 API Key 失败')
  } finally {
    setApiKeyActionLoading(item.id, false)
  }
}

const openOrgApiKeyDialog = (invitation: InvitationCode) => {
  if (!invitation.org_id) {
    ElMessage.warning('该企业尚未绑定组织ID，无法创建 API Key')
    return
  }

  resetApiKeyForm()
  apiKeyTargetOrgName.value = invitation.org_name || invitation.name
  apiKeyForm.value = {
    name: `${invitation.name} OpenAPI Key`,
    org_id: invitation.org_id,
    access_scope: 'single_org',
    rate_limit: 60
  }
  apiKeyDialogVisible.value = true
}

const openAllOrgsApiKeyDialog = () => {
  if (orgOptions.value.length === 0) {
    ElMessage.warning('当前没有可用企业，请先创建至少一个企业邀请码')
    return
  }

  const defaultOwner = orgOptions.value[0]
  resetApiKeyForm()
  apiKeyTargetOrgName.value = defaultOwner.name
  apiKeyForm.value = {
    name: 'OpenClaw all_orgs Key',
    org_id: defaultOwner.id,
    access_scope: 'all_orgs',
    rate_limit: 60
  }
  apiKeyDialogVisible.value = true
}

const handleCreateApiKey = async () => {
  if (!apiKeyForm.value.name.trim()) {
    ElMessage.warning('请输入 API Key 名称')
    return
  }
  if (!apiKeyForm.value.org_id && apiKeyForm.value.access_scope === 'all_orgs') {
    const fallbackOwner = orgOptions.value[0]
    if (fallbackOwner) {
      apiKeyForm.value.org_id = fallbackOwner.id
      apiKeyTargetOrgName.value = fallbackOwner.name
    }
  }
  if (!apiKeyForm.value.org_id) {
    ElMessage.warning('请选择归属企业')
    return
  }

  apiKeyLoading.value = true
  try {
    const created = await apiKeysApi.create({
      name: apiKeyForm.value.name.trim(),
      org_id: apiKeyForm.value.org_id,
      access_scope: apiKeyForm.value.access_scope,
      permissions: defaultOpenApiPermissions,
      rate_limit: apiKeyForm.value.rate_limit
    })
    apiKeyTargetOrgName.value = getOrgNameById(apiKeyForm.value.org_id)
    apiKeyResult.value = created.api_key
    await loadApiKeys()
    ElMessage.success('API Key 已创建，请立即复制并安全保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建 API Key 失败')
  } finally {
    apiKeyLoading.value = false
  }
}

const copyGeneratedApiKey = async () => {
  if (!apiKeyResult.value) {
    return
  }
  try {
    await navigator.clipboard.writeText(apiKeyResult.value)
    ElMessage.success('API Key 已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 创建邀请码
const handleCreate = async () => {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入企业名称')
    return
  }

  createLoading.value = true
  try {
    const data: CreateInvitationRequest = {
      name: createForm.value.name.trim(),
      max_uses: createForm.value.max_uses || 1,
      org_type: createForm.value.org_type
    }
    if (createForm.value.description?.trim()) {
      data.description = createForm.value.description.trim()
    }
    if (createForm.value.expires_at) {
      const expiresDate = new Date(createForm.value.expires_at)
      const diffMs = expiresDate.getTime() - Date.now()
      const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
      if (diffDays > 0) {
        data.expires_days = diffDays
      }
    }
    if (createForm.value.region_code.trim()) {
      data.region_code = createForm.value.region_code.trim()
    }
    if (createForm.value.region_name.trim()) {
      data.region_name = createForm.value.region_name.trim()
    }
    if (createForm.value.park_code.trim()) {
      data.park_code = createForm.value.park_code.trim()
    }
    if (createForm.value.park_name.trim()) {
      data.park_name = createForm.value.park_name.trim()
    }
    if (createForm.value.industry_type.trim()) {
      data.industry_type = createForm.value.industry_type.trim()
    }
    if (createForm.value.jurisdiction_level) {
      data.jurisdiction_level = createForm.value.jurisdiction_level
    }
    if (createForm.value.jurisdiction_codes.length > 0) {
      const codes = createForm.value.jurisdiction_codes.map(code => code.trim()).filter(Boolean)
      if (codes.length > 0) {
        data.jurisdiction_codes = codes
      }
    }

    const result = await invitationsApi.create(data)
    ElMessage.success(`邀请码创建成功: ${result.code}`)
    createDialogVisible.value = false
    await loadInvitations()
    await loadApiKeys()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '创建邀请码失败')
  } finally {
    createLoading.value = false
  }
}

// 复制邀请码
const copyCode = async (code: string) => {
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('邀请码已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

// 切换启用状态
const toggleStatus = async (invitation: InvitationCode) => {
  try {
    await invitationsApi.update(invitation.id, {
      is_active: !invitation.is_active
    })
    ElMessage.success(invitation.is_active ? '已禁用' : '已启用')
    await loadInvitations()
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '操作失败')
  }
}

// 删除邀请码（级联删除企业及关联数据，保留监测数据）
const handleDelete = async (invitation: InvitationCode) => {
  try {
    await ElMessageBox.confirm(
      `<div style="text-align: left; line-height: 1.8;">
        <p><strong>确定要删除邀请码 "${invitation.name}" 吗？</strong></p>
        <p style="color: #f56c6c; margin-top: 8px;">此操作将永久删除以下数据：</p>
        <ul style="margin: 8px 0; padding-left: 20px; color: #606266;">
          <li>该企业的所有用户账号（无法再登录）</li>
          <li>该企业的所有设备信息</li>
          <li>该企业的所有自检报告</li>
          <li>企业信息本身</li>
        </ul>
        <p style="color: #67c23a; margin-top: 8px;">
          <strong>保留数据：</strong>历史监测数据将作为数据沉淀保留
        </p>
        <p style="color: #f56c6c; font-weight: bold; margin-top: 8px;">删除操作不可恢复！</p>
      </div>`,
      '删除企业确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: true
      }
    )

    await invitationsApi.delete(invitation.id)
    ElMessage.success('企业已删除，历史监测数据已保留')
    await loadInvitations()
    await loadApiKeys()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error?.response?.data?.detail || '删除失败')
    }
  }
}

// 格式化日期
const formatDate = (dateStr: string | null) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// 获取状态标签类型
const getStatusType = (invitation: InvitationCode) => {
  if (!invitation.is_active) return 'info'
  if (invitation.status === 'active') return 'success'
  if (invitation.status === 'used') return 'warning'
  if (invitation.status === 'expired') return 'danger'
  return 'info'
}

// 获取状态文本
const getStatusText = (invitation: InvitationCode) => {
  if (!invitation.is_active) return '已禁用'
  if (invitation.status === 'active') return '可用'
  if (invitation.status === 'used') return '已用完'
  if (invitation.status === 'expired') return '已过期'
  return '未知'
}

const getOrgTypeLabel = (invitation: InvitationCode) => {
  if (invitation.org_type === 'regulator') return '监管'
  return '企业'
}

const formatJurisdiction = (invitation: InvitationCode) => {
  if (invitation.org_type !== 'regulator') return '-'
  const level = invitation.jurisdiction_level === 'park' ? '园区' : '区县'
  const codes = invitation.jurisdiction_codes?.join(', ') || '-'
  return `${level}: ${codes}`
}

const formatScopeOption = (option: JurisdictionOption) => {
  if (option.name) return `${option.code} ${option.name}`
  return option.code
}

const loadScopeOptions = async (level: string) => {
  if (!level) {
    scopeOptions.value = []
    return
  }

  scopeLoading.value = true
  try {
    scopeOptions.value = await organizationApi.getScopes({
      level: level === 'park' ? 'park' : 'district'
    })
  } catch (error: any) {
    scopeOptions.value = []
    ElMessage.error(error?.response?.data?.detail || '加载管辖编码失败')
  } finally {
    scopeLoading.value = false
  }
}

watch(
  () => createForm.value.org_type,
  value => {
    if (value !== 'regulator') {
      createForm.value.jurisdiction_level = ''
      createForm.value.jurisdiction_codes = []
      scopeOptions.value = []
    }
  }
)

watch(
  () => createForm.value.jurisdiction_level,
  value => {
    createForm.value.jurisdiction_codes = []
    if (!value) {
      scopeOptions.value = []
      return
    }
    loadScopeOptions(value)
  }
)

onMounted(() => {
  if (isSuperAdmin.value) {
    loadInvitations()
    loadApiKeys()
  }
})
</script>

<template>
  <div class="invitations-page">
    <!-- 非超级管理员提示 -->
    <div v-if="!isSuperAdmin" class="no-permission">
      <div class="no-permission-content">
        <svg class="no-permission-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <h2>无权限访问</h2>
        <p>邀请码管理仅限超级管理员使用</p>
      </div>
    </div>

    <!-- 超级管理员界面 -->
    <template v-else>
      <!-- 顶部操作栏 -->
      <div class="page-header">
        <div class="header-info">
          <h2 class="page-subtitle">管理企业注册邀请码</h2>
        </div>
        <div class="header-actions">
          <el-button @click="openAllOrgsApiKeyDialog">
            生成 all_orgs Key
          </el-button>
          <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          创建邀请码
          </el-button>
        </div>
      </div>

      <!-- 邀请码列表 -->
      <div class="invitations-container">
        <el-table
          v-loading="loading"
          :data="invitations"
          style="width: 100%"
          :header-cell-style="{ background: '#FAFAFA', color: '#1D1D1F', fontWeight: '600' }"
        >
          <el-table-column label="邀请码" min-width="180">
            <template #default="{ row }">
              <div class="code-cell">
                <code class="invitation-code">{{ row.code }}</code>
                <el-button
                  :icon="CopyDocument"
                  size="small"
                  text
                  @click="copyCode(row.code)"
                  title="复制邀请码"
                />
              </div>
            </template>
          </el-table-column>

          <el-table-column prop="name" label="组织名称" min-width="150" />

          <el-table-column label="类型" width="90">
            <template #default="{ row }">
              {{ getOrgTypeLabel(row) }}
            </template>
          </el-table-column>

          <el-table-column label="管辖范围" min-width="180">
            <template #default="{ row }">
              {{ formatJurisdiction(row) }}
            </template>
          </el-table-column>

          <el-table-column label="使用情况" width="120">
            <template #default="{ row }">
              <span :class="{ 'used-up': row.used_count >= row.max_uses }">
                {{ row.used_count }} / {{ row.max_uses }}
              </span>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getStatusType(row)" size="small">
                {{ getStatusText(row) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="过期时间" width="170">
            <template #default="{ row }">
              {{ formatDate(row.expires_at) }}
            </template>
          </el-table-column>

          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>

          <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
              <el-button
                link
                size="small"
                class="action-btn text-only"
                @click="openOrgApiKeyDialog(row)"
              >
                生成Key
              </el-button>
              <el-button
                link
                size="small"
                class="action-btn text-only"
                @click="toggleStatus(row)"
              >
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
              <el-button
                link
                size="small"
                class="action-btn text-only danger-btn"
                :icon="Delete"
                @click="handleDelete(row)"
              />
            </template>
          </el-table-column>
        </el-table>

        <!-- 空状态 -->
        <div v-if="!loading && invitations.length === 0" class="empty-state">
          <svg class="empty-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <p>暂无邀请码</p>
          <el-button type="primary" @click="openCreateDialog">创建第一个邀请码</el-button>
        </div>
      </div>

      <!-- 创建邀请码对话框 -->
      <div class="api-keys-container">
        <div class="section-header">
          <div class="section-title-group">
            <h3 class="section-title">已生成 API Key</h3>
            <span class="section-count">共 {{ filteredApiKeys.length }} 个</span>
          </div>
          <div class="section-actions">
            <el-select v-model="apiKeyScopeFilter" style="width: 150px">
              <el-option label="全部范围" value="all" />
              <el-option label="single_org" value="single_org" />
              <el-option label="all_orgs" value="all_orgs" />
            </el-select>
            <el-select
              v-model="apiKeyOrgFilter"
              clearable
              filterable
              placeholder="全部企业"
              style="width: 220px"
            >
              <el-option
                v-for="item in orgOptions"
                :key="item.id"
                :label="item.name"
                :value="item.id"
              />
            </el-select>
            <el-input
              v-model="apiKeyNameKeyword"
              clearable
              placeholder="搜索 Key 名称"
              style="width: 220px"
            />
            <el-button @click="loadApiKeys">刷新列表</el-button>
          </div>
        </div>

        <el-table
          v-loading="apiKeysLoading"
          :data="pagedApiKeys"
          style="width: 100%"
          :header-cell-style="{ background: '#FAFAFA', color: '#1D1D1F', fontWeight: '600' }"
        >
          <el-table-column prop="name" label="Key名称" min-width="180" />

          <el-table-column label="API Key" min-width="240">
            <template #default="{ row }">
              <div class="key-cell">
                <code class="api-key-code">{{ maskApiKey(row.api_key) }}</code>
                <el-button
                  :icon="CopyDocument"
                  size="small"
                  text
                  @click="copyApiKey(row.api_key)"
                  title="复制 API Key"
                />
              </div>
            </template>
          </el-table-column>

          <el-table-column label="访问范围" width="120">
            <template #default="{ row }">
              <el-tag :type="getApiKeyScopeType(row.access_scope)" size="small">
                {{ getApiKeyScopeLabel(row.access_scope) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="归属企业" min-width="180">
            <template #default="{ row }">
              {{ getOrgNameById(row.org_id) || row.org_id }}
            </template>
          </el-table-column>

          <el-table-column label="权限" width="120">
            <template #default="{ row }">
              <el-tooltip
                v-if="parsePermissions(row.permissions).length > 0"
                :content="parsePermissions(row.permissions).join(', ')"
                placement="top"
              >
                <span>{{ formatPermissions(row.permissions) }}</span>
              </el-tooltip>
              <span v-else>{{ formatPermissions(row.permissions) }}</span>
            </template>
          </el-table-column>

          <el-table-column prop="rate_limit" label="限流/分钟" width="100" />

          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="getApiKeyStatusType(row.is_active)" size="small">
                {{ getApiKeyStatusText(row.is_active) }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="创建时间" width="170">
            <template #default="{ row }">
              {{ formatDate(row.created_at) }}
            </template>
          </el-table-column>

          <el-table-column label="操作" width="180" fixed="right">
            <template #default="{ row }">
              <el-button
                link
                size="small"
                class="action-btn text-only"
                :loading="isApiKeyActionLoading(row.id)"
                @click="toggleApiKeyStatus(row)"
              >
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
              <el-button
                link
                size="small"
                class="action-btn text-only danger-btn"
                :loading="isApiKeyActionLoading(row.id)"
                @click="revokeApiKey(row)"
              >
                吊销
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div v-if="!apiKeysLoading && filteredApiKeys.length > 0" class="api-key-pagination">
          <el-pagination
            v-model:current-page="apiKeyCurrentPage"
            v-model:page-size="apiKeyPageSize"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            :total="filteredApiKeys.length"
          />
        </div>

        <div v-if="!apiKeysLoading && filteredApiKeys.length === 0" class="empty-state">
          <p>暂无 API Key</p>
        </div>
      </div>

      <el-dialog
        v-model="createDialogVisible"
        title="创建邀请码"
        width="480px"
        :close-on-click-modal="false"
      >
        <el-form :model="createForm" label-width="100px" label-position="left">
          <el-form-item label="组织类型" required>
            <el-select v-model="createForm.org_type" placeholder="选择类型" style="width: 100%">
              <el-option label="企业" value="enterprise" />
              <el-option label="监管部门" value="regulator" />
            </el-select>
          </el-form-item>

          <el-form-item label="企业名称" required>
            <el-input
              v-model="createForm.name"
              placeholder="输入企业或组织名称"
              maxlength="100"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="描述">
            <el-input
              v-model="createForm.description"
              type="textarea"
              placeholder="可选，备注信息"
              :rows="2"
              maxlength="500"
            />
          </el-form-item>

          <el-form-item label="区域编码">
            <el-input v-model="createForm.region_code" placeholder="如区县编码" />
          </el-form-item>

          <el-form-item label="区域名称">
            <el-input v-model="createForm.region_name" placeholder="如区县名称" />
          </el-form-item>

          <el-form-item label="园区编码">
            <el-input v-model="createForm.park_code" placeholder="如园区编码" />
          </el-form-item>

          <el-form-item label="园区名称">
            <el-input v-model="createForm.park_name" placeholder="如园区名称" />
          </el-form-item>

          <el-form-item label="行业类型">
            <el-input v-model="createForm.industry_type" placeholder="行业编码 (可选)" />
          </el-form-item>

          <el-form-item v-if="createForm.org_type === 'regulator'" label="管辖层级">
            <el-select v-model="createForm.jurisdiction_level" placeholder="选择层级" style="width: 100%">
              <el-option label="区县" value="district" />
              <el-option label="园区" value="park" />
            </el-select>
          </el-form-item>

          <el-form-item v-if="createForm.org_type === 'regulator'" label="管辖编码">
            <el-select
              v-model="createForm.jurisdiction_codes"
              multiple
              filterable
              allow-create
              default-first-option
              :loading="scopeLoading"
              :disabled="!createForm.jurisdiction_level"
              placeholder="输入并回车添加"
              style="width: 100%"
            >
              <el-option
                v-for="option in scopeOptions"
                :key="option.code"
                :label="formatScopeOption(option)"
                :value="option.code"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="可用次数">
            <el-input-number
              v-model="createForm.max_uses"
              :min="1"
              :max="1000"
              controls-position="right"
            />
            <span class="form-hint">该邀请码可注册的用户数量</span>
          </el-form-item>

          <el-form-item label="过期时间">
            <el-date-picker
              v-model="createForm.expires_at"
              type="datetime"
              placeholder="可选，不设置则永不过期"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
            />
          </el-form-item>
        </el-form>

        <template #footer>
          <el-button @click="createDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="createLoading" @click="handleCreate">
            创建
          </el-button>
        </template>
      </el-dialog>

      <el-dialog
        v-model="apiKeyDialogVisible"
        title="生成 OpenAPI Key"
        width="560px"
        :close-on-click-modal="false"
        @closed="resetApiKeyForm"
      >
        <div v-if="!apiKeyResult">
          <el-alert
            type="info"
            show-icon
            :closable="false"
            title="默认会赋予 6 个 P0 工具权限，可用于 OpenClaw 联调"
            class="api-key-alert"
          />

          <el-form :model="apiKeyForm" label-width="110px" label-position="left">
            <el-form-item label="访问范围">
              <el-tag :type="apiKeyForm.access_scope === 'all_orgs' ? 'warning' : 'success'">
                {{ apiKeyForm.access_scope }}
              </el-tag>
            </el-form-item>

            <el-form-item label="Key 名称" required>
              <el-input v-model="apiKeyForm.name" maxlength="128" show-word-limit />
            </el-form-item>

            <el-form-item v-if="apiKeyForm.access_scope === 'single_org'" label="归属企业">
              <el-input :model-value="apiKeyTargetOrgName || getOrgNameById(apiKeyForm.org_id)" disabled />
            </el-form-item>

            <el-form-item label="限流(次/分钟)">
              <el-input-number
                v-model="apiKeyForm.rate_limit"
                :min="1"
                :max="600"
                controls-position="right"
              />
            </el-form-item>

            <el-form-item v-if="apiKeyForm.access_scope === 'all_orgs'" label="提示">
              <span class="form-hint no-left-margin">
                all_orgs 模式下系统自动设置审计归属；调用 OpenAPI 时必须传 enterprise_name 或 org_id。
              </span>
            </el-form-item>
          </el-form>
        </div>

        <div v-else class="api-key-result">
          <el-alert
            type="warning"
            show-icon
            :closable="false"
            title="API Key 仅展示在当前窗口，请立即复制并妥善保管"
            class="api-key-alert"
          />
          <div class="api-key-result-meta">
            <span>
              {{ apiKeyForm.access_scope === 'all_orgs' ? '审计归属' : '归属企业' }}：
              {{ apiKeyTargetOrgName || getOrgNameById(apiKeyForm.org_id) }}
            </span>
            <span>访问范围：{{ apiKeyForm.access_scope }}</span>
          </div>
          <el-input :model-value="apiKeyResult" readonly type="textarea" :rows="3" />
        </div>

        <template #footer>
          <el-button @click="apiKeyDialogVisible = false">关闭</el-button>
          <el-button
            v-if="apiKeyResult"
            type="primary"
            :icon="CopyDocument"
            @click="copyGeneratedApiKey"
          >
            复制 Key
          </el-button>
          <el-button
            v-else
            type="primary"
            :loading="apiKeyLoading"
            @click="handleCreateApiKey"
          >
            生成 Key
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<style scoped>
.invitations-page {
  min-height: 100%;
}

/* 无权限提示 */
.no-permission {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.no-permission-content {
  text-align: center;
  color: #86868B;
}

.no-permission-icon {
  width: 64px;
  height: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.no-permission-content h2 {
  font-size: 20px;
  font-weight: 600;
  color: #1D1D1F;
  margin-bottom: 8px;
}

.no-permission-content p {
  font-size: 14px;
}

/* 页面头部 */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-subtitle {
  font-size: 14px;
  color: #86868B;
  font-weight: 400;
  margin: 0;
}

/* 邀请码容器 */
.invitations-container {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.api-keys-container {
  margin-top: 20px;
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.section-title-group {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.section-title {
  margin: 0;
  font-size: 16px;
  color: #1d1d1f;
  font-weight: 600;
}

.section-count {
  font-size: 13px;
  color: #86868b;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.api-key-pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

/* 邀请码单元格 */
.code-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.key-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.invitation-code {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 13px;
  background: #F5F5F7;
  padding: 4px 8px;
  border-radius: 6px;
  color: #1D1D1F;
  letter-spacing: 0.5px;
}

.api-key-code {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
  font-size: 12px;
  background: #f5f5f7;
  padding: 4px 8px;
  border-radius: 6px;
  color: #1d1d1f;
  letter-spacing: 0.4px;
}

.used-up {
  color: #FF3B30;
  font-weight: 500;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #86868B;
}

.empty-icon {
  width: 48px;
  height: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state p {
  margin-bottom: 16px;
  font-size: 14px;
}

.action-btn.text-only {
  padding: 6px 12px;
  color: #1D1D1F;
  font-size: 13px;
  font-weight: 500;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 0;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transition: all 0.2s ease;
}

.action-btn.text-only:hover {
  color: #0B1727;
  border-color: rgba(11, 23, 39, 0.2);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
  background: #fafafa;
  text-decoration: none;
}

.danger-btn.text-only {
  color: #1D1D1F;
}

.danger-btn.text-only:hover {
  color: #C41E3A;
  border-color: rgba(196, 30, 58, 0.2);
  box-shadow: 0 4px 12px rgba(196, 30, 58, 0.12);
}

/* 表单提示 */
.form-hint {
  font-size: 12px;
  color: #86868B;
  margin-left: 12px;
}

.form-hint.no-left-margin {
  margin-left: 0;
}

.api-key-alert {
  margin-bottom: 16px;
}

.api-key-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.api-key-result-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: #606266;
}

/* 表格样式优化 */
:deep(.el-table) {
  --el-table-border-color: #F0F0F0;
  --el-table-row-hover-bg-color: #FAFAFA;
}

:deep(.el-table th.el-table__cell) {
  font-size: 13px;
}

:deep(.el-table td.el-table__cell) {
  font-size: 14px;
}

/* 对话框样式 */
:deep(.el-dialog) {
  border-radius: 16px;
}

:deep(.el-dialog__header) {
  padding: 20px 24px 16px;
  border-bottom: 1px solid #F0F0F0;
}

:deep(.el-dialog__title) {
  font-size: 18px;
  font-weight: 600;
}

:deep(.el-dialog__body) {
  padding: 24px;
}

:deep(.el-dialog__footer) {
  padding: 16px 24px 20px;
  border-top: 1px solid #F0F0F0;
}
</style>
