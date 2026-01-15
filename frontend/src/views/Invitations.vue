<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { invitationsApi, type InvitationCode, type CreateInvitationRequest } from '@/api/invitations'
import { organizationApi, type JurisdictionOption } from '@/api/organizations'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, CopyDocument, Delete } from '@element-plus/icons-vue'

const authStore = useAuthStore()
const loading = ref(false)
const invitations = ref<InvitationCode[]>([])

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
        <el-button type="primary" :icon="Plus" @click="openCreateDialog">
          创建邀请码
        </el-button>
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

          <el-table-column label="操作" width="170" fixed="right">
            <template #default="{ row }">
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

/* 邀请码单元格 */
.code-cell {
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
