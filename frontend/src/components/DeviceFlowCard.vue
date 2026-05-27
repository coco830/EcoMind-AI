<template>
  <el-card class="device-flow-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <el-icon class="header-icon"><Odometer /></el-icon>
          <span class="header-title">实时流量监测</span>
        </div>
        <div class="header-right">
          <el-tag type="info" size="small" effect="plain">
            数据来源：数采仪
          </el-tag>
          <el-button
            type="primary"
            link
            :loading="loading"
            @click="fetchData"
          >
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
      </div>
    </template>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="3" animated />
    </div>

    <!-- 无数据状态 -->
    <el-empty
      v-else-if="!deviceData || deviceData.devices.length === 0"
      description="暂无设备流量数据"
      :image-size="80"
    />

    <!-- 设备列表 -->
    <div v-else class="device-list">
      <div
        v-for="device in deviceData.devices"
        :key="device.device_id"
        class="device-item"
      >
        <!-- 设备信息头 -->
        <div class="device-header">
          <div class="device-info">
            <span class="device-name">{{ device.device_name }}</span>
            <el-tag
              :type="getStatusType(device.device_status)"
              size="small"
              effect="plain"
            >
              {{ getStatusText(device.device_status) }}
            </el-tag>
          </div>
          <span class="device-mn">MN: {{ device.device_id }}</span>
        </div>

        <!-- 流量显示 -->
        <div class="flow-display">
          <div class="flow-value" :class="{ 'no-data': device.latest_flow === null }">
            {{ device.latest_flow !== null ? device.latest_flow.toFixed(2) : '--' }}
            <span class="flow-unit">{{ device.flow_unit }}</span>
          </div>
          <div class="flow-label">瞬时流量</div>
          <div v-if="device.latest_flow_ts" class="flow-time">
            更新: {{ formatTime(device.latest_flow_ts) }}
          </div>
        </div>

        <!-- 趋势图（可折叠） -->
        <el-collapse
          v-if="device.trend_data && device.trend_data.length > 0"
          @change="() => handleCollapseChange(device.device_id)"
        >
          <el-collapse-item title="流量趋势" name="trend">
            <div ref="chartRef" class="flow-chart" :id="`chart-${device.device_id}`"></div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </div>

    <!-- 数据来源说明 -->
    <div class="source-note">
      <el-icon><InfoFilled /></el-icon>
      <span>{{ deviceData?.data_source_note || '此数据来自环境监测数采仪，仅供参考，不存储到自检报告' }}</span>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { Odometer, Refresh, InfoFilled } from '@element-plus/icons-vue'
import { selfInspectionApi, type DeviceFlowListResponse, type DeviceFlowData } from '@/api/selfInspection'
import { ElMessage } from 'element-plus/es/components/message/index'
import * as echarts from '@/plugins/echarts'

// Props
interface Props {
  hours?: number
  includeHistory?: boolean
  autoRefresh?: boolean
  refreshInterval?: number // 毫秒
  targetOrgId?: string // 超级管理员指定的目标组织ID
}

const props = withDefaults(defineProps<Props>(), {
  hours: 24,
  includeHistory: true,
  autoRefresh: false,
  refreshInterval: 60000, // 默认1分钟刷新一次
  targetOrgId: ''
})

// Emits
const emit = defineEmits<{
  (e: 'loaded', data: DeviceFlowListResponse): void
  (e: 'error', error: Error): void
}>()

// State
const loading = ref(false)
const deviceData = ref<DeviceFlowListResponse | null>(null)
const chartInstances = ref<Map<string, echarts.ECharts>>(new Map())
let refreshTimer: ReturnType<typeof setInterval> | null = null

// Methods
const fetchData = async () => {
  loading.value = true
  try {
    const data = await selfInspectionApi.getDeviceFlow({
      hours: props.hours,
      include_history: props.includeHistory,
      target_org_id: props.targetOrgId || undefined
    })
    deviceData.value = data
    emit('loaded', data)

    // 渲染图表
    await nextTick()
    renderCharts()
  } catch (error: any) {
    console.error('Failed to fetch device flow data:', error)
    ElMessage.error('获取流量数据失败')
    emit('error', error)
  } finally {
    loading.value = false
  }
}

const renderCharts = () => {
  if (!deviceData.value) return

  for (const device of deviceData.value.devices) {
    if (device.trend_data && device.trend_data.length > 0) {
      const chartDom = document.getElementById(`chart-${device.device_id}`)
      if (!chartDom) continue

      // 销毁旧实例
      const existingChart = chartInstances.value.get(device.device_id)
      if (existingChart) {
        existingChart.dispose()
      }

      // 创建新实例
      const chart = echarts.init(chartDom)
      chartInstances.value.set(device.device_id, chart)

      const option: echarts.EChartsOption = {
        tooltip: {
          trigger: 'axis',
          formatter: (params: any) => {
            const data = params[0]
            return `${formatTime(data.axisValue)}<br/>流量: ${data.value.toFixed(2)} ${device.flow_unit}`
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '8%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: device.trend_data.map(p => p.ts),
          axisLabel: {
            formatter: (value: string) => {
              const date = new Date(value)
              return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`
            }
          }
        },
        yAxis: {
          type: 'value',
          name: device.flow_unit,
          axisLabel: {
            formatter: '{value}'
          }
        },
        series: [
          {
            name: '瞬时流量',
            type: 'line',
            smooth: true,
            data: device.trend_data.map(p => p.value),
            areaStyle: {
              opacity: 0.3
            },
            lineStyle: {
              color: '#409EFF'
            },
            itemStyle: {
              color: '#409EFF'
            }
          }
        ]
      }

      chart.setOption(option)
    }
  }
}

const handleCollapseChange = async (deviceId: string) => {
  // ECharts 在隐藏容器中初始化时可能出现宽高为 0，展开后需要 resize
  await nextTick()
  const chart = chartInstances.value.get(deviceId)
  if (chart) {
    chart.resize()
  } else {
    renderCharts()
  }
}

const getStatusType = (status: DeviceFlowData['device_status']) => {
  const types: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    online: 'success',
    offline: 'danger',
    alarm: 'warning',
    unknown: 'info'
  }
  return types[status] || 'info'
}

const getStatusText = (status: DeviceFlowData['device_status']) => {
  const texts: Record<string, string> = {
    online: '在线',
    offline: '离线',
    alarm: '告警',
    unknown: '未知'
  }
  return texts[status] || '未知'
}

const formatTime = (ts: string) => {
  const date = new Date(ts)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`
}

// 自动刷新
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

// Lifecycle
onMounted(() => {
  fetchData()
  startAutoRefresh()
})

// Watch
watch(() => props.autoRefresh, (newVal) => {
  if (newVal) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

// 监听组织ID变化，重新获取数据
watch(() => props.targetOrgId, () => {
  fetchData()
})

// Cleanup
import { onUnmounted } from 'vue'
onUnmounted(() => {
  stopAutoRefresh()
  // 销毁所有图表实例
  chartInstances.value.forEach(chart => chart.dispose())
  chartInstances.value.clear()
})

// Expose
defineExpose({
  refresh: fetchData
})
</script>

<style scoped>
.device-flow-card {
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

.flow-display {
  text-align: center;
  padding: 16px 0;
}

.flow-value {
  font-size: 36px;
  font-weight: 600;
  color: #409EFF;
  line-height: 1.2;
}

.flow-value.no-data {
  color: #909399;
}

.flow-unit {
  font-size: 16px;
  font-weight: normal;
  color: #606266;
  margin-left: 4px;
}

.flow-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.flow-time {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 8px;
}

.flow-chart {
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

.source-note .el-icon {
  font-size: 14px;
}

:deep(.el-collapse-item__header) {
  font-size: 13px;
  color: #606266;
}

:deep(.el-collapse-item__content) {
  padding-bottom: 0;
}
</style>
