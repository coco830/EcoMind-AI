<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { deviceApi, type Device, type DeviceCreate, type ThresholdConfig, type PollutantThreshold, POLLUTANT_OPTIONS } from '@/api/devices'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const loading = ref(false)
const devices = ref<Device[]>([])
const dialogVisible = ref(false)
const dialogTitle = ref('添加设备')
const formRef = ref<FormInstance>()
const editingId = ref<string | null>(null)

// Default threshold config
const getDefaultThresholdConfig = (deviceType: string): ThresholdConfig => {
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
  latitude: undefined,
  longitude: undefined,
  address: '',
  thresholds: getDefaultThresholdConfig('water')
})

// Watch for device type changes and update threshold config
watch(() => form.value.device_type, (newType) => {
  if (!editingId.value) {
    // Only auto-update for new devices
    form.value.thresholds = getDefaultThresholdConfig(newType)
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
    devices.value = await deviceApi.list()
  } catch (error) {
    ElMessage.error('加载设备列表失败')
  } finally {
    loading.value = false
  }
}

const openDialog = (device?: Device) => {
  if (device) {
    dialogTitle.value = '编辑设备'
    editingId.value = device.id
    form.value = {
      mn: device.mn,
      name: device.name,
      device_type: device.device_type,
      org_id: device.org_id,  // 编辑时保留原来的org_id
      latitude: device.latitude || undefined,
      longitude: device.longitude || undefined,
      address: device.address || '',
      thresholds: device.thresholds || getDefaultThresholdConfig(device.device_type)
    }
  } else {
    dialogTitle.value = '添加设备'
    editingId.value = null
    form.value = {
      mn: '',
      name: '',
      device_type: 'water',
      // 不传 org_id，后端会自动使用当前用户的组织
      latitude: undefined,
      longitude: undefined,
      address: '',
      thresholds: getDefaultThresholdConfig('water')
    }
  }
  dialogVisible.value = true
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

// Check if user has permission to modify devices
const canModifyDevices = computed(() => {
  const role = authStore.user?.role
  return role === 'admin' || role === 'operator'
})

onMounted(loadDevices)
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
        <el-table-column prop="device_type" label="类型" width="120">
          <template #default="{ row }">
            {{ getDeviceTypeLabel(row.device_type) }}
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
        <el-form-item label="位置">
          <el-input v-model="form.address" placeholder="设备安装位置" />
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

        <template v-if="form.thresholds?.enabled">
          <el-table :data="form.thresholds!.pollutants" size="small" border>
            <el-table-column prop="pollutant_name" label="污染物" width="100" />
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
            <el-table-column prop="unit" label="单位" width="80" />
          </el-table>
          <div class="threshold-hint">
            预警值触发黄色预警，报警值触发红色告警。
          </div>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
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
