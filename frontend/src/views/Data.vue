<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { dataApi, type MonitoringData } from '@/api/data'
import { deviceApi, type Device } from '@/api/devices'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'

const loading = ref(false)
const devices = ref<Device[]>([])
const data = ref<MonitoringData[]>([])
const selectedDevice = ref('')
const dateRange = ref<[Date, Date] | null>(null)

let chart: echarts.ECharts | null = null

const loadDevices = async () => {
  try {
    devices.value = await deviceApi.list()
    if (devices.value.length > 0) {
      selectedDevice.value = devices.value[0].mn
    }
  } catch (error) {
    ElMessage.error('加载设备列表失败')
  }
}

const loadData = async () => {
  if (!selectedDevice.value) return

  loading.value = true
  try {
    const params: Record<string, string> = {
      device_id: selectedDevice.value,
      limit: '1000'
    }

    if (dateRange.value) {
      params.start_time = dateRange.value[0].toISOString()
      params.end_time = dateRange.value[1].toISOString()
    }

    data.value = await dataApi.getHistory(selectedDevice.value, params)
    updateChart()
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const updateChart = () => {
  if (!chart) return

  const chartData = data.value.slice().reverse()
  const times = chartData.map(d => new Date(d.ts).toLocaleString())
  const values = chartData.map(d => d.value)

  chart.setOption({
    title: { text: '监测数据趋势', left: 'center' },
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => {
        const p = (params as { data: number; axisValue: string }[])[0]
        return `${p.axisValue}<br/>数值: ${p.data}`
      }
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { rotate: 45 }
    },
    yAxis: { type: 'value', name: '数值' },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100 }
    ],
    series: [{
      data: values,
      type: 'line',
      smooth: true,
      areaStyle: { opacity: 0.3 },
      markLine: {
        data: [{ type: 'average', name: '平均值' }]
      }
    }]
  })
}

const initChart = () => {
  const chartDom = document.getElementById('data-chart')
  if (chartDom) {
    chart = echarts.init(chartDom)
  }
}

const handleExport = async (format: 'json' | 'csv') => {
  if (!selectedDevice.value) {
    ElMessage.warning('请选择设备')
    return
  }

  try {
    const params: Record<string, string> = {
      device_id: selectedDevice.value,
      format
    }

    if (dateRange.value) {
      params.start_time = dateRange.value[0].toISOString()
      params.end_time = dateRange.value[1].toISOString()
    }

    const result = await dataApi.export(params)

    if (format === 'csv') {
      const blob = new Blob([result.data as string], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `data_${selectedDevice.value}_${Date.now()}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } else {
      const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `data_${selectedDevice.value}_${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
    }

    ElMessage.success('导出成功')
  } catch {
    ElMessage.error('导出失败')
  }
}

const getFlagType = (flag: string) => {
  const types: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    N: 'success',
    F: 'danger',
    D: 'danger',
    M: 'warning',
    C: 'warning',
    T: 'danger',
    B: 'danger'
  }
  return types[flag] || 'info'
}

onMounted(async () => {
  initChart()
  await loadDevices()
  if (selectedDevice.value) {
    loadData()
  }
})

onUnmounted(() => {
  if (chart) chart.dispose()
})
</script>

<template>
  <div class="data-page">
    <el-card class="query-card">
      <div class="query-bar">
        <el-select
          v-model="selectedDevice"
          placeholder="选择设备"
          @change="loadData"
        >
          <el-option
            v-for="device in devices"
            :key="device.id"
            :label="`${device.name} (${device.mn})`"
            :value="device.mn"
          />
        </el-select>

        <el-date-picker
          v-model="dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          @change="loadData"
        />

        <el-button type="primary" @click="loadData">
          <el-icon><Search /></el-icon>
          查询
        </el-button>

        <el-dropdown @command="handleExport">
          <el-button>
            导出 <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="csv">导出CSV</el-dropdown-item>
              <el-dropdown-item command="json">导出JSON</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </el-card>

    <el-card class="chart-card">
      <div id="data-chart" style="height: 400px"></div>
    </el-card>

    <el-card class="table-card">
      <template #header>
        <span>数据明细 (共 {{ data.length }} 条)</span>
      </template>
      <el-table :data="data" v-loading="loading" stripe max-height="400">
        <el-table-column prop="ts" label="时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.ts).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column prop="device_id" label="设备ID" width="180" />
        <el-table-column prop="pollutant_code" label="污染物编码" width="120" />
        <el-table-column prop="value" label="数值" width="120">
          <template #default="{ row }">
            {{ row.value.toFixed(4) }}
          </template>
        </el-table-column>
        <el-table-column prop="flag" label="标志位" width="80">
          <template #default="{ row }">
            <el-tag :type="getFlagType(row.flag)" size="small">
              {{ row.flag }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.data-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.query-bar {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.chart-card,
.table-card {
  width: 100%;
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

/* 默认按钮（导出按钮等） */
:deep(.el-button--default),
:deep(.el-dropdown__caret-button),
:deep(.el-dropdown .el-button),
:deep(.el-button--default:not(:hover)),
:deep(.el-dropdown .el-button:not(:hover)) {
  border-color: #dcdfe6 !important;
  color: #606266 !important;
  background-color: #fff !important;
}

:deep(.el-button--default:hover),
:deep(.el-dropdown__caret-button:hover),
:deep(.el-dropdown .el-button:hover) {
  border-color: #0B1727 !important;
  color: #0B1727 !important;
  background-color: rgba(11, 23, 39, 0.06) !important;
}

:deep(.el-button--default:active),
:deep(.el-dropdown__caret-button:active),
:deep(.el-dropdown .el-button:active) {
  border-color: #0B1727 !important;
  color: #0B1727 !important;
  background-color: rgba(11, 23, 39, 0.1) !important;
}

/* 确保 focus 状态不会持续 */
:deep(.el-button--default:focus:not(:hover)),
:deep(.el-dropdown .el-button:focus:not(:hover)) {
  border-color: #dcdfe6 !important;
  color: #606266 !important;
  background-color: #fff !important;
}
</style>
