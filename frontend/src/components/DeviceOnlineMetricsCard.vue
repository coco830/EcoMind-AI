<template>
  <el-card class="device-online-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><DataLine /></el-icon>
          <span class="header-title">在线数据监测</span>
        </div>
        <div class="header-right">
          <el-tag type="info" size="small" effect="plain">对账用（非监控）</el-tag>
          <el-button type="primary" link @click="toggleExpanded">
            {{ expanded ? '收起' : '展开' }}
          </el-button>
          <el-button v-if="expanded" type="primary" link :loading="loading" @click="fetchAll">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
      </div>
    </template>

    <div v-if="!expanded" class="collapsed-hint">
      默认收起，避免与驾驶舱重复；仅用于对账/交叉验证（设备→指标→趋势）。
    </div>

    <div v-show="expanded">
      <div class="toolbar">
        <el-select
          v-model="selectedPollutant"
          placeholder="选择在线指标"
          filterable
          style="width: 260px"
          :loading="optionsLoading"
        >
          <el-option
            v-for="opt in options"
            :key="opt.pollutant_code"
            :label="`${opt.pollutant_name} (${opt.pollutant_code})`"
            :value="opt.pollutant_code"
          />
        </el-select>

        <el-checkbox v-model="includeHistory">包含趋势</el-checkbox>
        <el-button size="small" @click="selectedPollutant = 'w00000'">瞬时流量</el-button>
      </div>

      <div v-if="loading" class="loading-container">
        <el-skeleton :rows="3" animated />
      </div>

      <el-empty
        v-else-if="!data || data.devices.length === 0"
        description="暂无在线数据（请确认已绑定设备且有数据上报）"
        :image-size="80"
      />

      <div v-else class="device-list">
        <div
          v-for="device in data.devices"
          :key="device.device_id"
          class="device-item"
        >
          <div class="device-header">
            <div class="device-info">
              <span class="device-name">{{ device.device_name }}</span>
              <el-tag :type="getStatusType(device.device_status)" size="small" effect="plain">
                {{ getStatusText(device.device_status) }}
              </el-tag>
            </div>
            <span class="device-mn">MN: {{ device.device_id }}</span>
          </div>

          <div class="metric-display">
            <div class="metric-value" :class="{ 'no-data': device.latest_value === null }">
              {{ device.latest_value !== null ? formatNumber(device.latest_value) : '--' }}
              <span class="metric-unit">{{ device.unit || data.unit || '' }}</span>
            </div>
            <div class="metric-label">{{ data.pollutant_name }}</div>
            <div v-if="device.latest_ts" class="metric-time">更新: {{ formatTime(device.latest_ts) }}</div>
          </div>

          <el-collapse
            v-if="device.trend_data && device.trend_data.length > 0"
            @change="() => handleCollapseChange(device.device_id)"
          >
            <el-collapse-item title="趋势" name="trend">
              <div class="metric-chart" :id="`metric-chart-${device.device_id}`"></div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </div>

      <div class="source-note">
        <el-icon><InfoFilled /></el-icon>
        <span>{{ data?.data_source_note || '数据来自环境监测数采仪（只读），不存储到自检报告' }}</span>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick, onUnmounted } from 'vue'
import { DataLine, Refresh, InfoFilled } from '@element-plus/icons-vue'
import * as echarts from '@/plugins/echarts'
import { ElMessage } from 'element-plus/es/components/message/index'
import { selfInspectionApi } from '@/api/selfInspection'

interface Props {
  hours?: number
  targetOrgId?: string
  autoRefresh?: boolean
  refreshInterval?: number
  defaultCollapsed?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  hours: 24,
  targetOrgId: '',
  autoRefresh: true,
  refreshInterval: 60000,
  defaultCollapsed: true
})

type MetricOption = { pollutant_code: string; pollutant_name: string; unit?: string | null }
type DeviceMetric = {
  device_id: string
  device_name: string
  device_status: 'online' | 'offline' | 'alarm' | 'unknown'
  latest_value: number | null
  latest_ts: string | null
  unit?: string | null
  trend_data?: Array<{ ts: string; value: number; flag: string }> | null
}
type MetricResponse = {
  pollutant_code: string
  pollutant_name: string
  unit?: string | null
  devices: DeviceMetric[]
  org_name: string
  query_time: string
  data_source_note: string
}

const loading = ref(false)
const optionsLoading = ref(false)
const options = ref<MetricOption[]>([])
const selectedPollutant = ref<string>('')
const includeHistory = ref(true)
const data = ref<MetricResponse | null>(null)
const expanded = ref(!props.defaultCollapsed)
const initialized = ref(false)

const chartInstances = ref<Map<string, echarts.ECharts>>(new Map())
let refreshTimer: ReturnType<typeof setInterval> | null = null

const loadOptions = async () => {
  optionsLoading.value = true
  try {
    const opts = await selfInspectionApi.getOnlineMetricOptions({
      hours: props.hours,
      target_org_id: props.targetOrgId || undefined
    })
    options.value = opts || []
    if (!selectedPollutant.value) {
      const preferred = options.value.find(o => o.pollutant_code === 'w00000')
      selectedPollutant.value = preferred?.pollutant_code || options.value[0]?.pollutant_code || ''
    }
  } catch (e: any) {
    console.error(e)
  } finally {
    optionsLoading.value = false
  }
}

const fetchData = async () => {
  if (!selectedPollutant.value) return
  loading.value = true
  try {
    const res = await selfInspectionApi.getDeviceOnlineMetrics({
      pollutant_code: selectedPollutant.value,
      hours: props.hours,
      include_history: includeHistory.value,
      target_org_id: props.targetOrgId || undefined
    })
    data.value = res
    await nextTick()
    renderCharts()
  } catch (e: any) {
    console.error('Failed to fetch online metrics:', e)
    ElMessage.error('获取在线数据失败')
  } finally {
    loading.value = false
  }
}

const fetchAll = async () => {
  await loadOptions()
  await fetchData()
  initialized.value = true
}

const renderCharts = () => {
  if (!data.value) return
  for (const device of data.value.devices) {
    if (!device.trend_data || device.trend_data.length === 0) continue
    const dom = document.getElementById(`metric-chart-${device.device_id}`)
    if (!dom) continue

    const existing = chartInstances.value.get(device.device_id)
    if (existing) existing.dispose()

    const chart = echarts.init(dom)
    chartInstances.value.set(device.device_id, chart)

    const option: echarts.EChartsOption = {
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const p = params[0]
          return `${formatTime(p.axisValue)}<br/>${data.value?.pollutant_name}: ${formatNumber(p.value)} ${data.value?.unit || ''}`
        }
      },
      grid: { left: '3%', right: '4%', bottom: '3%', top: '8%', containLabel: true },
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: device.trend_data.map(p => p.ts),
        axisLabel: {
          formatter: (value: string) => {
            const d = new Date(value)
            return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
          }
        }
      },
      yAxis: { type: 'value', name: data.value?.unit || '', axisLabel: { formatter: '{value}' } },
      series: [
        {
          name: data.value.pollutant_name,
          type: 'line',
          smooth: true,
          data: device.trend_data.map(p => p.value),
          areaStyle: { opacity: 0.2 },
          lineStyle: { color: '#409EFF' },
          itemStyle: { color: '#409EFF' }
        }
      ]
    }
    chart.setOption(option)
  }
}

const handleCollapseChange = async (deviceId: string) => {
  await nextTick()
  const chart = chartInstances.value.get(deviceId)
  if (chart) chart.resize()
  else renderCharts()
}

const startAutoRefresh = () => {
  if (props.autoRefresh && !refreshTimer) {
    refreshTimer = setInterval(fetchData, props.refreshInterval)
  }
}
const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

const getStatusType = (status: DeviceMetric['device_status']) => {
  const types: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    online: 'success',
    offline: 'danger',
    alarm: 'warning',
    unknown: 'info'
  }
  return types[status] || 'info'
}
const getStatusText = (status: DeviceMetric['device_status']) => {
  const texts: Record<string, string> = { online: '在线', offline: '离线', alarm: '告警', unknown: '未知' }
  return texts[status] || '未知'
}
const formatTime = (ts: string) => {
  const d = new Date(ts)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}
const formatNumber = (v: number) => {
  if (!Number.isFinite(v)) return String(v)
  if (Math.abs(v) >= 100) return v.toFixed(1)
  if (Math.abs(v) >= 1) return v.toFixed(2)
  return v.toFixed(4)
}

onMounted(async () => {
  if (expanded.value) {
    await fetchAll()
    startAutoRefresh()
  }
})

watch(() => props.targetOrgId, async () => {
  data.value = null
  selectedPollutant.value = ''
  if (expanded.value) {
    await fetchAll()
  }
})

watch(selectedPollutant, () => {
  if (expanded.value) fetchData()
})

watch(includeHistory, () => {
  if (expanded.value) fetchData()
})

watch(() => props.autoRefresh, (newVal) => {
  if (!expanded.value) return
  if (newVal) startAutoRefresh()
  else stopAutoRefresh()
})

const toggleExpanded = async () => {
  expanded.value = !expanded.value
  if (!expanded.value) {
    stopAutoRefresh()
    return
  }
  if (!initialized.value) {
    await fetchAll()
  } else {
    await fetchData()
  }
  startAutoRefresh()
}

onUnmounted(() => {
  stopAutoRefresh()
  chartInstances.value.forEach(c => c.dispose())
  chartInstances.value.clear()
})
</script>

<style scoped>
.device-online-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 20px;
  color: #409EFF;
}

.header-title {
  font-size: 16px;
  font-weight: 500;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 0 4px;
}

.collapsed-hint {
  padding: 10px 12px;
  color: #909399;
  font-size: 13px;
  background: #f8f9fb;
  border: 1px dashed #e4e7ed;
  border-radius: 8px;
}

.loading-container {
  padding: 20px;
}

.device-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.device-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
}

.device-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed #e4e7ed;
}

.device-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-name {
  font-weight: 500;
  color: #303133;
}

.device-mn {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.metric-display {
  text-align: center;
  padding: 16px 0;
}

.metric-value {
  font-size: 34px;
  font-weight: 600;
  color: #409EFF;
  line-height: 1.2;
}

.metric-value.no-data {
  color: #909399;
}

.metric-unit {
  font-size: 14px;
  font-weight: normal;
  color: #606266;
  margin-left: 4px;
}

.metric-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.metric-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 8px;
}

.metric-chart {
  width: 100%;
  height: 200px;
  margin-top: 8px;
}

.source-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 16px;
  padding: 8px 12px;
  background: #fdf6ec;
  border-radius: 4px;
  font-size: 12px;
  color: #e6a23c;
}
</style>
