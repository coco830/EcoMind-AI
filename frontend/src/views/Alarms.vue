<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { alarmApi, type Alarm } from '@/api/alarms'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const alarms = ref<Alarm[]>([])
const statusFilter = ref('')
const levelFilter = ref('')
const typeFilter = ref('')

const filteredAlarms = computed(() => {
  return alarms.value.filter(a => {
    if (statusFilter.value && a.status !== statusFilter.value) return false
    if (levelFilter.value && a.level !== levelFilter.value) return false
    if (typeFilter.value && a.alarm_type !== typeFilter.value) return false
    return true
  })
})

const loadAlarms = async () => {
  loading.value = true
  try {
    alarms.value = await alarmApi.list({ limit: 500 })
  } catch {
    ElMessage.error('加载告警列表失败')
  } finally {
    loading.value = false
  }
}

const handleAcknowledge = async (alarm: Alarm) => {
  try {
    await alarmApi.acknowledge(alarm.id)
    ElMessage.success('确认成功')
    loadAlarms()
  } catch {
    ElMessage.error('确认失败')
  }
}

const handleResolve = async (alarm: Alarm) => {
  try {
    await ElMessageBox.confirm('确定要将此告警标记为已解决吗？', '确认', { type: 'info' })
    await alarmApi.resolve(alarm.id)
    ElMessage.success('处理成功')
    loadAlarms()
  } catch {
    // Cancelled
  }
}

const handleDelete = async (alarm: Alarm) => {
  try {
    await ElMessageBox.confirm('确定要删除此告警记录吗？', '确认删除', { type: 'warning' })
    await alarmApi.delete(alarm.id)
    ElMessage.success('删除成功')
    loadAlarms()
  } catch {
    // Cancelled
  }
}

const getLevelType = (level: string) => {
  const types: Record<string, 'info' | 'warning' | 'danger'> = {
    info: 'info',
    warning: 'warning',
    critical: 'danger'
  }
  return types[level] || 'info'
}

const getStatusType = (status: string) => {
  const types: Record<string, 'info' | 'warning' | 'success'> = {
    pending: 'warning',
    acknowledged: 'info',
    resolved: 'success'
  }
  return types[status] || 'info'
}

const getAlarmTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    threshold: '阈值超标',
    anomaly: 'AI异常',
    offline: '设备离线',
    flag: '标志异常'
  }
  return labels[type] || type
}

const getAlarmTypeTag = (type: string) => {
  const styles: Record<string, { type: 'primary' | 'success' | 'warning' | 'danger' | 'info'; icon: string }> = {
    threshold: { type: 'danger', icon: '!' },
    anomaly: { type: 'primary', icon: 'AI' },
    offline: { type: 'info', icon: '~' },
    flag: { type: 'warning', icon: 'F' }
  }
  return styles[type] || { type: 'info', icon: '?' }
}

const getPollutantName = (code: string | null) => {
  if (!code) return '-'
  const names: Record<string, string> = {
    'w01018': 'COD',
    'w21003': '氨氮',
    'w01001': 'pH值',
    'w01010': '总磷',
    'w21011': '总氮',
    'a34004': 'PM2.5',
    'a34002': 'PM10',
    'a21004': 'NO2',
    'a21026': 'SO2',
    'a05024': 'O3',
  }
  return names[code] || code
}

const getLevelLabel = (level: string) => {
  const labels: Record<string, string> = {
    info: '提示',
    warning: '警告',
    critical: '严重'
  }
  return labels[level] || level
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    pending: '待处理',
    acknowledged: '已确认',
    resolved: '已解决'
  }
  return labels[status] || status
}

onMounted(loadAlarms)
</script>

<template>
  <div class="alarms-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>告警管理</span>
          <el-button @click="loadAlarms">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <div class="filter-bar">
        <el-select v-model="statusFilter" placeholder="状态筛选" clearable>
          <el-option label="待处理" value="pending" />
          <el-option label="已确认" value="acknowledged" />
          <el-option label="已解决" value="resolved" />
        </el-select>
        <el-select v-model="levelFilter" placeholder="级别筛选" clearable>
          <el-option label="提示" value="info" />
          <el-option label="警告" value="warning" />
          <el-option label="严重" value="critical" />
        </el-select>
        <el-select v-model="typeFilter" placeholder="来源筛选" clearable>
          <el-option label="阈值超标" value="threshold" />
          <el-option label="AI异常" value="anomaly" />
          <el-option label="设备离线" value="offline" />
          <el-option label="标志异常" value="flag" />
        </el-select>
      </div>

      <el-table :data="filteredAlarms" v-loading="loading" stripe>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column prop="level" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="getLevelType(row.level)" size="small">
              {{ getLevelLabel(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="alarm_type" label="来源" width="110">
          <template #default="{ row }">
            <el-tag :type="getAlarmTypeTag(row.alarm_type).type" size="small">
              {{ getAlarmTypeLabel(row.alarm_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pollutant_code" label="污染物" width="80">
          <template #default="{ row }">
            {{ getPollutantName(row.pollutant_code) }}
          </template>
        </el-table-column>
        <el-table-column prop="message" label="告警信息" min-width="250" />
        <el-table-column prop="device_id" label="设备ID" width="150" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              type="primary"
              link
              @click="handleAcknowledge(row)"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status !== 'resolved'"
              type="success"
              link
              @click="handleResolve(row)"
            >
              解决
            </el-button>
            <el-button type="danger" link @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
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
</style>
