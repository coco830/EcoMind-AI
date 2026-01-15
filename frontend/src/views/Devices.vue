<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import { deviceApi, type Device, type DeviceCreate, type ThresholdConfig, type IndustryType, type IndustryTypeInfo, POLLUTANT_OPTIONS, getWaterThresholdTemplate } from '@/api/devices'
import { organizationApi, type Organization } from '@/api/organizations'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

// Organization filter for superadmin
const organizations = ref<Organization[]>([])
const selectedOrgId = ref<string>('')

const loading = ref(false)
const devices = ref<Device[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('添加设备')
const formRef = ref<FormInstance>()
const editingId = ref<string | null>(null)
const industryTypes = ref<IndustryTypeInfo[]>([])
const templateLabel = computed(() => {
  if (form.value.device_type !== 'water') return '默认模板'
  const info = industryTypes.value.find(t => t.code === form.value.industry_type)
  return info ? `${info.name}（${info.standard}）` : '通用废水模板'
})
const amapReady = ref(false)
const amapLoading = ref(false)
const amapError = ref<string | null>(null)
let AMap: any = null
let geocoder: any = null
let autoComplete: any = null
const addressInputId = 'device-address-input'

// Default threshold config
const getDefaultThresholdConfig = (deviceType: string, industryType?: IndustryType): ThresholdConfig => {
  if (deviceType === 'water') {
    return getWaterThresholdTemplate(industryType)
  }
  const pollutants = POLLUTANT_OPTIONS[deviceType as keyof typeof POLLUTANT_OPTIONS] || []
  return {
    enabled: true,
    pollutants: pollutants.map(p => ({
      pollutant_code: p.code,
      pollutant_name: p.name,
      warning_value: p.defaultWarning,
      alarm_value: p.defaultAlarm,
      unit: p.unit,
    }))
  }
}

const form = ref<DeviceCreate>({
  mn: '',
  name: '',
  device_type: 'water',
  industry_type: undefined,
  national_standard: '',
  latitude: undefined,
  longitude: undefined,
  address: '',
  thresholds: getDefaultThresholdConfig('water', undefined)
})

// 当行业类型改变时，自动填充执行标准
const handleIndustryTypeChange = (industryType: IndustryType | undefined) => {
  if (industryType) {
    const info = industryTypes.value.find(t => t.code === industryType)
    if (info) {
      form.value.national_standard = info.standard
    }
  } else {
    form.value.national_standard = ''
  }

  // 水质设备切换行业时，自动加载对应模板（新建时生效，编辑时不强制覆盖）
  if (form.value.device_type === 'water' && !editingId.value) {
    form.value.thresholds = getDefaultThresholdConfig('water', industryType)
  }
}

// 获取行业类型名称
const getIndustryTypeName = (type: IndustryType | null): string => {
  if (!type) return '-'
  const info = industryTypes.value.find(t => t.code === type)
  return info ? info.name : type
}

// 获取组织名称
const getOrganizationName = (orgId: string | null): string => {
  if (!orgId) return '-'
  const org = organizations.value.find(o => o.id === orgId)
  return org ? org.name : orgId
}

// Watch for device type changes and update threshold config
watch(() => form.value.device_type, (newType) => {
  if (!editingId.value) {
    // Only auto-update for new devices
    form.value.thresholds = getDefaultThresholdConfig(newType, form.value.industry_type)
  }
})

const rules: FormRules = {
  mn: [{ required: true, message: '请输入设备MN号', trigger: 'blur' }],
  name: [{ required: true, message: '请输入设备名称', trigger: 'blur' }],
  device_type: [{ required: true, message: '请选择设备类型', trigger: 'change' }]
}

const statusFilter = ref('')
const typeFilter = ref('')

const filteredDevices = computed(() => {
  return devices.value.filter(d => {
    if (statusFilter.value && d.status !== statusFilter.value) return false
    if (typeFilter.value && d.device_type !== typeFilter.value) return false
    return true
  })
})

const loadDevices = async () => {
  loading.value = true
  try {
    const params: { org_id?: string } = {}
    if (selectedOrgId.value) {
      params.org_id = selectedOrgId.value
    }
    devices.value = await deviceApi.list(params)
  } catch (error) {
    ElMessage.error('加载设备列表失败')
  } finally {
    loading.value = false
  }
}

// Watch for organization filter changes
watch(selectedOrgId, () => {
  loadDevices()
})

const loadIndustryTypes = async () => {
  try {
    industryTypes.value = await deviceApi.getIndustryTypes()
  } catch (error) {
    console.error('加载行业类型失败:', error)
  }
}

const openDialog = (device?: Device) => {
  // 重置地理编码缓存
  lastGeocodedAddress = ''

  if (device) {
    dialogTitle.value = '编辑设备'
    editingId.value = device.id
    form.value = {
      mn: device.mn,
      name: device.name,
      device_type: device.device_type,
      org_id: device.org_id,  // 编辑时保留原来的org_id
      industry_type: device.industry_type || undefined,
      national_standard: device.national_standard || '',
      latitude: device.latitude || undefined,
      longitude: device.longitude || undefined,
      address: device.address || '',
      thresholds: device.thresholds || getDefaultThresholdConfig(device.device_type)
    }
    // 记录已有地址，避免编辑时重复地理编码
    if (device.address) {
      lastGeocodedAddress = device.address
    }
  } else {
    dialogTitle.value = '添加设备'
    editingId.value = null
    form.value = {
      mn: '',
      name: '',
      device_type: 'water',
      industry_type: undefined,
      national_standard: '',
      // 超级管理员需要选择组织，否则后端会自动使用当前用户的组织
      org_id: isSuperAdmin.value ? (selectedOrgId.value || undefined) : undefined,
      latitude: undefined,
      longitude: undefined,
      address: '',
      thresholds: getDefaultThresholdConfig('water', undefined)
    }
  }
  dialogVisible.value = true
  nextTick(() => {
    setupAmapEnhancements()
  })
}

const handleSubmit = async () => {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  try {
    if (editingId.value) {
      await deviceApi.update(editingId.value, form.value)
      ElMessage.success('设备更新成功')
    } else {
      await deviceApi.create(form.value)
      ElMessage.success('设备创建成功')
    }
    dialogVisible.value = false
    loadDevices()
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

const ensureThresholds = () => {
  if (!form.value.thresholds) {
    form.value.thresholds = getDefaultThresholdConfig(form.value.device_type, form.value.industry_type)
  }
}

const applyIndustryTemplate = () => {
  if (form.value.device_type !== 'water') {
    ElMessage.info('当前仅水质设备支持行业模板，其他类型请手动配置。')
    return
  }
  form.value.thresholds = getDefaultThresholdConfig('water', form.value.industry_type)
  ElMessage.success(`已按 ${templateLabel.value} 填充阈值，可继续调整`)
}

const addPollutantRow = () => {
  ensureThresholds()
  form.value.thresholds!.pollutants.push({
    pollutant_code: '',
    pollutant_name: '自定义指标',
    unit: '',
    warning_value: 0,
    alarm_value: 0
  })
}

const removePollutantRow = (index: number) => {
  if (!form.value.thresholds) return
  form.value.thresholds.pollutants.splice(index, 1)
}

const keepFlowOnly = () => {
  ensureThresholds()
  if (!form.value.thresholds) return
  const flowCodes = ['w00001', 'flow']
  const filtered = form.value.thresholds.pollutants.filter(p => {
    const code = (p.pollutant_code || '').toLowerCase()
    const name = (p.pollutant_name || '').toLowerCase()
    return flowCodes.some(c => code.includes(c) || name.includes('流量'))
  })
  if (filtered.length === 0) {
    ElMessage.warning('未找到流量指标，已保留原有指标')
    return
  }
  form.value.thresholds.pollutants = filtered
  ElMessage.success('已仅保留流量指标，其他请按需添加')
}

// --- AMap helpers: autocomplete + geocoder + map picker ---
const ensureAmap = async () => {
  if (amapReady.value || amapLoading.value) return
  amapLoading.value = true
  try {
    const key = import.meta.env.VITE_AMAP_KEY
    const securityJsCode = import.meta.env.VITE_AMAP_SECURITY_CODE
    if (!key || !securityJsCode) {
      amapError.value = '缺少高德地图 Key 或安全码'
      return
    }
    ;(window as any)._AMapSecurityConfig = {
      securityJsCode
    }
    AMap = await AMapLoader.load({
      key,
      version: '2.0',
      plugins: ['AMap.AutoComplete', 'AMap.Geocoder']
    })
    geocoder = new AMap.Geocoder()
    amapReady.value = true
  } catch (err: any) {
    amapError.value = err?.message || '高德地图加载失败'
  } finally {
    amapLoading.value = false
  }
}

const setupAutoComplete = () => {
  if (!AMap || !geocoder) return
  // 解绑旧实例
  if (autoComplete) {
    autoComplete.off('select')
  }
  autoComplete = new AMap.AutoComplete({
    input: addressInputId,
    city: '全国'
  })
  autoComplete.on('select', (e: any) => {
    const value = e.poi?.name || e.poi?.district || form.value.address
    if (value) {
      geocoder.getLocation(value, (status: string, result: any) => {
        if (status === 'complete' && result.geocodes?.length) {
          const loc = result.geocodes[0].location
          form.value.address = result.geocodes[0].formattedAddress || value
          form.value.longitude = loc.lng
          form.value.latitude = loc.lat
        }
      })
    }
  })
}

// 上次地理编码的地址，避免重复请求
let lastGeocodedAddress = ''

// 根据地址自动获取经纬度
const geocodeAddress = () => {
  if (!geocoder || !form.value.address?.trim()) return

  const address = form.value.address.trim()

  // 如果地址没变且已有经纬度，跳过
  if (address === lastGeocodedAddress && form.value.longitude && form.value.latitude) return

  geocoder.getLocation(address, (status: string, result: any) => {
    if (status === 'complete' && result.geocodes?.length) {
      const loc = result.geocodes[0].location
      form.value.longitude = loc.lng
      form.value.latitude = loc.lat
      lastGeocodedAddress = address
    }
  })
}

const setupAmapEnhancements = async () => {
  await ensureAmap()
  if (!amapReady.value) return
  setupAutoComplete()
}

const handleDelete = async (device: Device) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除设备 "${device.name}" 吗？`,
      '确认删除',
      { type: 'warning' }
    )
    await deviceApi.delete(device.id)
    ElMessage.success('删除成功')
    loadDevices()
  } catch {
    // User cancelled
  }
}

const getStatusType = (status: string) => {
  const types: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
    online: 'success',
    offline: 'info',
    alarm: 'danger',
    maintenance: 'warning'
  }
  return types[status] || 'info'
}

const getDeviceTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    water: '水质监测',
    air: '大气监测',
    noise: '噪声监测',
    soil: '土壤监测'
  }
  return labels[type] || type
}

// Check if user has permission to modify devices (superadmin only)
const canModifyDevices = computed(() => {
  return authStore.user?.is_superadmin === true
})

// Check if user is superadmin
const isSuperAdmin = computed(() => {
  return authStore.user?.is_superadmin === true
})

// Platform staff (superadmin/doc_editor/viewer) can filter by organization for demo/ops
const canFilterByOrg = computed(() => {
  return authStore.user?.is_superadmin === true || authStore.user?.role === 'doc_editor' || authStore.user?.role === 'viewer'
})

// Load organizations for superadmin
const loadOrganizations = async () => {
  if (!canFilterByOrg.value) return
  try {
    organizations.value = await organizationApi.list()
  } catch (error) {
    console.error('加载组织列表失败:', error)
  }
}

onMounted(() => {
  loadDevices()
  loadIndustryTypes()
  loadOrganizations()
})
</script>

<template>
  <div class="devices-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>设备管理</span>
          <el-button v-if="canModifyDevices" type="primary" @click="openDialog()">
            <el-icon><Plus /></el-icon>
            添加设备
          </el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-select
          v-if="canFilterByOrg"
          v-model="selectedOrgId"
          placeholder="筛选企业"
          clearable
          filterable
          style="width: 200px"
        >
          <el-option
            v-for="org in organizations"
            :key="org.id"
            :label="org.name"
            :value="org.id"
          />
        </el-select>
        <el-select v-model="statusFilter" placeholder="状态筛选" clearable>
          <el-option label="在线" value="online" />
          <el-option label="离线" value="offline" />
          <el-option label="告警" value="alarm" />
          <el-option label="维护" value="maintenance" />
        </el-select>
        <el-select v-model="typeFilter" placeholder="类型筛选" clearable>
          <el-option label="水质监测" value="water" />
          <el-option label="大气监测" value="air" />
          <el-option label="噪声监测" value="noise" />
          <el-option label="土壤监测" value="soil" />
        </el-select>
      </div>

      <el-table :data="filteredDevices" v-loading="loading" stripe>
        <el-table-column prop="mn" label="MN号" width="180" />
        <el-table-column prop="name" label="设备名称" min-width="150" />
        <el-table-column v-if="canFilterByOrg" label="所属企业" width="150">
          <template #default="{ row }">
            {{ getOrganizationName(row.org_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="device_type" label="类型" width="100">
          <template #default="{ row }">
            {{ getDeviceTypeLabel(row.device_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="industry_type" label="所属行业" width="140">
          <template #default="{ row }">
            {{ getIndustryTypeName(row.industry_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="national_standard" label="执行标准" width="130">
          <template #default="{ row }">
            <el-tooltip v-if="row.national_standard" :content="row.national_standard" placement="top">
              <span>{{ row.national_standard }}</span>
            </el-tooltip>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="address" label="位置" min-width="200" />
        <el-table-column prop="last_heartbeat" label="最后心跳" width="180">
          <template #default="{ row }">
            {{ row.last_heartbeat ? new Date(row.last_heartbeat).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column v-if="canModifyDevices" label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="openDialog(row)">编辑</el-button>
            <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="MN号" prop="mn">
          <el-input v-model="form.mn" placeholder="设备唯一标识" />
        </el-form-item>
        <el-form-item label="设备名称" prop="name">
          <el-input v-model="form.name" placeholder="设备名称" />
        </el-form-item>
        <el-form-item label="设备类型" prop="device_type">
          <el-select v-model="form.device_type" style="width: 100%">
            <el-option label="水质监测" value="water" />
            <el-option label="大气监测" value="air" />
            <el-option label="噪声监测" value="noise" />
            <el-option label="土壤监测" value="soil" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isSuperAdmin" label="所属企业" prop="org_id" :rules="[{ required: true, message: '请选择所属企业', trigger: 'change' }]">
          <el-select
            v-model="form.org_id"
            placeholder="请选择企业"
            filterable
            style="width: 100%"
          >
            <el-option
              v-for="org in organizations"
              :key="org.id"
              :label="org.name"
              :value="org.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属行业">
          <el-select
            v-model="form.industry_type"
            placeholder="请选择所属行业"
            clearable
            style="width: 100%"
            @change="handleIndustryTypeChange"
          >
            <el-option
              v-for="industry in industryTypes"
              :key="industry.code"
              :label="industry.name"
              :value="industry.code"
            >
              <span>{{ industry.name }}</span>
              <span style="float: right; color: #8492a6; font-size: 12px">{{ industry.standard }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="执行标准">
          <el-input
            v-model="form.national_standard"
            placeholder="执行的国家或地方排放标准（选择行业后自动填充）"
          />
        </el-form-item>
        <el-form-item label="位置">
          <el-input
            v-model="form.address"
            :id="addressInputId"
            placeholder="输入企业详细地址（自动识别经纬度）"
            clearable
            @blur="geocodeAddress"
          />
          <div v-if="amapError" class="amap-hint error">{{ amapError }}</div>
          <div v-else class="amap-hint">输入详细地址后自动识别经纬度坐标</div>
        </el-form-item>
        <el-form-item label="经纬度">
          <el-row :gutter="10">
            <el-col :span="12">
              <el-input-number
                v-model="form.latitude"
                :precision="6"
                placeholder="纬度"
                style="width: 100%"
              />
            </el-col>
            <el-col :span="12">
              <el-input-number
                v-model="form.longitude"
                :precision="6"
                placeholder="经度"
                style="width: 100%"
              />
            </el-col>
          </el-row>
        </el-form-item>

        <!-- Threshold Configuration Section -->
        <el-divider content-position="left">阈值配置</el-divider>

        <el-form-item label="启用阈值">
          <el-switch v-model="form.thresholds!.enabled" />
        </el-form-item>

        <el-form-item label="快速填充" v-if="form.device_type === 'water'">
          <div class="threshold-actions">
            <el-button class="ghost-btn" plain @click="applyIndustryTemplate">
              按行业模板填充
            </el-button>
            <el-button class="ghost-btn" plain @click="addPollutantRow">
              添加自定义指标
            </el-button>
            <el-button class="ghost-btn" plain @click="keepFlowOnly">
              仅保留流量
            </el-button>
          </div>
          <div class="threshold-hint">
            当前模板：{{ templateLabel }}，可在表格中继续调整或新增指标。
          </div>
        </el-form-item>

        <template v-if="form.thresholds?.enabled">
          <div class="threshold-table-wrap">
            <el-table :data="form.thresholds!.pollutants" size="small" border>
            <el-table-column label="指标名称" min-width="140">
              <template #default="{ row }">
                <el-input v-model="row.pollutant_name" size="small" placeholder="名称" />
              </template>
            </el-table-column>
            <el-table-column label="预警值" width="150">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.warning_value"
                  :precision="2"
                  :min="0"
                  size="small"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="报警值" width="150">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.alarm_value"
                  :precision="2"
                  :min="0"
                  size="small"
                  style="width: 100%"
                />
              </template>
            </el-table-column>
            <el-table-column label="单位" width="100">
              <template #default="{ row }">
                <el-input v-model="row.unit" size="small" placeholder="单位" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70">
              <template #default="scope">
                <el-button link size="small" class="remove-btn" @click="removePollutantRow(scope.$index)">-</el-button>
              </template>
            </el-table-column>
            </el-table>
          </div>
          <div class="threshold-hint">
            预警值触发黄色预警，报警值触发红色告警。
            <el-button link size="small" class="add-btn" @click="addPollutantRow">+ 添加指标</el-button>
          </div>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>

  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.threshold-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

.threshold-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ghost-btn,
.link-ghost-btn {
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.08);
  color: #0B1727;
  background: #fff;
}

.ghost-btn:hover,
.link-ghost-btn:hover {
  color: #0B3A99;
  border-color: rgba(11, 58, 153, 0.25);
  box-shadow: 0 8px 20px rgba(11, 58, 153, 0.14);
}

.ghost-btn:focus,
.link-ghost-btn:focus {
  box-shadow: 0 0 0 2px rgba(11, 58, 153, 0.16);
}

.link-ghost-btn {
  border-radius: 0;
  margin-left: 6px;
}

.remove-btn {
  font-weight: 700;
  font-size: 16px;
  color: #0B1727;
}

.remove-btn:hover {
  color: #0B3A99;
}

.add-btn {
  margin-left: 12px;
  color: #0B1727;
}

.add-btn:hover {
  color: #0B3A99;
  text-decoration: underline;
}

.amap-hint {
  margin-top: 6px;
  font-size: 12px;
  color: #6B7280;
}

.amap-hint.error {
  color: #D92D20;
}

:deep(.el-table__body-wrapper) {
  overflow-x: auto;
  overflow-y: auto;
}

:deep(.el-table__body-wrapper::-webkit-scrollbar) {
  height: 8px;
  width: 8px;
}

:deep(.el-table__body-wrapper::-webkit-scrollbar-thumb) {
  background: rgba(0, 0, 0, 0.25);
  border-radius: 4px;
}

:deep(.el-table__body-wrapper::-webkit-scrollbar-track) {
  background: rgba(0, 0, 0, 0.06);
}

.threshold-table-wrap {
  max-height: 280px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
  border-radius: 4px;
}

.threshold-table-wrap::-webkit-scrollbar {
  width: 6px;
}

.threshold-table-wrap::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 3px;
}

.threshold-table-wrap::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.04);
}

/* 统一按钮样式 - 深蓝色 #0B1727 */
:deep(.el-button--primary) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
}

:deep(.el-button--primary:hover),
:deep(.el-button--primary:focus) {
  background-color: #162a3d !important;
  border-color: #162a3d !important;
}

:deep(.el-button--primary:active) {
  background-color: #0a1320 !important;
  border-color: #0a1320 !important;
}

/* 删除按钮 - 深红色填充，白色文字 */
:deep(.el-button--danger) {
  background-color: #C41E3A !important;
  border-color: #C41E3A !important;
  color: #fff !important;
}

:deep(.el-button--danger:hover),
:deep(.el-button--danger:focus) {
  background-color: #D63850 !important;
  border-color: #D63850 !important;
}

:deep(.el-button--danger:active) {
  background-color: #A31830 !important;
  border-color: #A31830 !important;
}

/* 默认按钮（取消按钮等） */
:deep(.el-button--default) {
  border-color: #dcdfe6 !important;
  color: #606266 !important;
  background-color: #fff !important;
}

:deep(.el-button--default:hover),
:deep(.el-button--default:focus) {
  border-color: #0B1727 !important;
  color: #0B1727 !important;
  background-color: rgba(11, 23, 39, 0.06) !important;
}

:deep(.el-button--default:active) {
  border-color: #0B1727 !important;
  color: #0B1727 !important;
  background-color: rgba(11, 23, 39, 0.1) !important;
}
</style>
