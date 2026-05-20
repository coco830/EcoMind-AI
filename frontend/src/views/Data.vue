<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { dataApi, type MonitoringData } from '@/api/data'
import { deviceApi, type Device } from '@/api/devices'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  getPollutantName,
  getPollutantUnit,
  getPollutantColor,
  formatPollutantValue,
  generateGroupedPollutantOptions,
} from '@/config/pollutants'

const loading = ref(false)
const devices = ref<Device[]>([])
const data = ref<MonitoringData[]>([])
const selectedDevice = ref('')
const selectedPollutants = ref<string[]>([])
const dateRange = ref<[Date, Date] | null>(null)
const timePreset = ref('24h')

let chart: echarts.ECharts | null = null

// 时间快捷选项
const timePresets = [
  { label: '24小时', value: '24h', hours: 24 },
  { label: '7天', value: '7d', hours: 168 },
  { label: '30天', value: '30d', hours: 720 },
  { label: '自定义', value: 'custom', hours: 0 },
]

// 分组的污染物选项
const groupedPollutantOptions = computed(() => generateGroupedPollutantOptions())

// 设备可用的污染物列表（从实际数据中提取）
const availablePollutants = ref<string[]>([])

// 统计数据
const statistics = computed(() => {
  if (data.value.length === 0) return null

  const statsByPollutant: Record<string, {
    code: string
    name: string
    unit: string
    count: number
    min: number
    max: number
    avg: number
    latest: number
    exceedCount: number
  }> = {}

  for (const item of data.value) {
    const code = item.pollutant_code
    if (!selectedPollutants.value.includes(code)) continue

    if (!statsByPollutant[code]) {
      statsByPollutant[code] = {
        code,
        name: getPollutantName(code),
        unit: getPollutantUnit(code),
        count: 0,
        min: Infinity,
        max: -Infinity,
        avg: 0,
        latest: 0,
        exceedCount: 0,
      }
    }

    const stats = statsByPollutant[code]
    stats.count++
    stats.min = Math.min(stats.min, item.value)
    stats.max = Math.max(stats.max, item.value)
    stats.avg += item.value
    stats.latest = item.value

    // 标记为异常的数据
    if (item.flag && item.flag !== 'N') {
      stats.exceedCount++
    }
  }

  // 计算平均值
  for (const code in statsByPollutant) {
    const stats = statsByPollutant[code]
    stats.avg = stats.count > 0 ? stats.avg / stats.count : 0
    if (stats.min === Infinity) stats.min = 0
    if (stats.max === -Infinity) stats.max = 0
  }

  return Object.values(statsByPollutant)
})

// 数据完整率
const dataCompleteness = computed(() => {
  if (!dateRange.value || data.value.length === 0) return null

  const start = dateRange.value[0].getTime()
  const end = dateRange.value[1].getTime()
  const hours = (end - start) / (1000 * 60 * 60)

  // 假设每小时应有1条数据
  const expectedCount = Math.ceil(hours) * selectedPollutants.value.length
  const actualCount = data.value.filter(d =>
    selectedPollutants.value.includes(d.pollutant_code)
  ).length

  return {
    expected: expectedCount,
    actual: actualCount,
    rate: expectedCount > 0 ? Math.min(100, (actualCount / expectedCount) * 100) : 0
  }
})

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
      limit: '5000'
    }

    // 设置时间范围
    if (timePreset.value !== 'custom') {
      const preset = timePresets.find(p => p.value === timePreset.value)
      if (preset && preset.hours > 0) {
        const end = new Date()
        const start = new Date(end.getTime() - preset.hours * 60 * 60 * 1000)
        params.start_time = start.toISOString()
        params.end_time = end.toISOString()
        dateRange.value = [start, end]
      }
    } else if (dateRange.value) {
      params.start_time = dateRange.value[0].toISOString()
      params.end_time = dateRange.value[1].toISOString()
    }

    data.value = await dataApi.getHistory(selectedDevice.value, params)

    // 提取可用的污染物列表
    const codes = new Set<string>()
    for (const item of data.value) {
      codes.add(item.pollutant_code)
    }
    availablePollutants.value = Array.from(codes)

    // 如果没有选择污染物，默认选择前3个
    if (selectedPollutants.value.length === 0 && availablePollutants.value.length > 0) {
      selectedPollutants.value = availablePollutants.value.slice(0, 3)
    }

    updateChart()
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const updateChart = () => {
  if (!chart || selectedPollutants.value.length === 0) {
    if (chart) {
      chart.setOption({
        title: { text: '历史数据趋势对比', left: 'center', top: 10 },
        series: []
      })
    }
    return
  }

  // 按污染物分组数据
  const groupedData: Record<string, MonitoringData[]> = {}
  for (const item of data.value) {
    if (!selectedPollutants.value.includes(item.pollutant_code)) continue
    if (!groupedData[item.pollutant_code]) {
      groupedData[item.pollutant_code] = []
    }
    groupedData[item.pollutant_code].push(item)
  }

  // 获取所有时间点并排序
  const allTimes = new Set<string>()
  for (const items of Object.values(groupedData)) {
    for (const item of items) {
      allTimes.add(item.ts)
    }
  }
  const sortedTimes = Array.from(allTimes).sort()
  const timeLabels = sortedTimes.map(t => {
    const d = new Date(t)
    return `${(d.getMonth() + 1).toString().padStart(2, '0')}/${d.getDate().toString().padStart(2, '0')} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  })

  // 构建系列数据
  const series: echarts.SeriesOption[] = []
  const legendData: string[] = []
  let index = 0

  for (const code of selectedPollutants.value) {
    const items = groupedData[code] || []
    const name = getPollutantName(code)
    const color = getPollutantColor(code, index)
    legendData.push(name)

    // 创建时间到值的映射
    const valueMap = new Map<string, number>()
    for (const item of items) {
      valueMap.set(item.ts, item.value)
    }

    // 按统一时间轴生成数据
    const values = sortedTimes.map(t => valueMap.get(t) ?? null)

    series.push({
      name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      showSymbol: false,
      data: values,
      lineStyle: { width: 2, color },
      itemStyle: { color },
      areaStyle: {
        opacity: 0.1,
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${color}40` },
            { offset: 1, color: `${color}05` }
          ]
        }
      },
      emphasis: {
        focus: 'series',
        itemStyle: { borderWidth: 2, borderColor: '#fff' }
      },
      connectNulls: false,
    })

    index++
  }

  chart.setOption({
    title: {
      text: '历史数据趋势对比',
      left: 'center',
      top: 10,
      textStyle: { fontSize: 16, fontWeight: 600, color: '#1D1D1F' }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.96)',
      borderColor: 'transparent',
      borderRadius: 12,
      padding: [12, 16],
      boxShadow: '0 4px 24px rgba(0, 0, 0, 0.12)',
      textStyle: { color: '#1D1D1F', fontSize: 13 },
      formatter: (params: unknown) => {
        const list = params as { seriesName: string; data: number | null; color: string; axisValue: string }[]
        if (!list || list.length === 0) return ''

        let result = `<div style="font-weight:600;margin-bottom:8px">${list[0].axisValue}</div>`
        for (const p of list) {
          if (p.data !== null && p.data !== undefined) {
            const code = selectedPollutants.value.find(c => getPollutantName(c) === p.seriesName) || ''
            const unit = getPollutantUnit(code)
            const formatted = formatPollutantValue(code, p.data)
            result += `<div style="display:flex;align-items:center;margin:4px 0">
              <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:8px"></span>
              <span>${p.seriesName}:</span>
              <span style="font-weight:600;margin-left:4px">${formatted}</span>
              <span style="color:#86868B;margin-left:2px">${unit}</span>
            </div>`
          }
        }
        return result
      }
    },
    legend: {
      data: legendData,
      bottom: 10,
      textStyle: { color: '#86868B', fontSize: 12 }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: timeLabels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#86868B', fontSize: 11, rotate: 45 },
      splitLine: { show: true, lineStyle: { color: 'rgba(0, 0, 0, 0.04)', type: 'dashed' } }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#86868B', fontSize: 11 },
      splitLine: { show: true, lineStyle: { color: 'rgba(0, 0, 0, 0.04)', type: 'dashed' } }
    },
    dataZoom: [
      { type: 'inside', start: 0, end: 100 },
      { type: 'slider', start: 0, end: 100, bottom: 35, height: 20 }
    ],
    series
  }, true)
}

const handleTimePresetChange = (value: string) => {
  timePreset.value = value
  if (value !== 'custom') {
    loadData()
  }
}

const handleDateRangeChange = () => {
  if (dateRange.value) {
    timePreset.value = 'custom'
    loadData()
  }
}

const handlePollutantChange = () => {
  updateChart()
}

const initChart = () => {
  const chartDom = document.getElementById('data-chart')
  if (chartDom) {
    chart = echarts.init(chartDom)
    window.addEventListener('resize', () => chart?.resize())
  }
}

const handleExport = async (format: 'json' | 'csv') => {
  if (!selectedDevice.value) {
    ElMessage.warning('请选择设备')
    return
  }

  try {
    const params: {
      device_id: string
      format: 'json' | 'csv'
      start_time?: string
      end_time?: string
    } = {
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

// 监听污染物选择变化
watch(selectedPollutants, () => {
  updateChart()
})

onMounted(async () => {
  initChart()
  await loadDevices()
  if (selectedDevice.value) {
    loadData()
  }
})

onUnmounted(() => {
  if (chart) {
    window.removeEventListener('resize', () => chart?.resize())
    chart.dispose()
  }
})
</script>

<template>
  <div class="data-page">
    <!-- 查询条件卡片 -->
    <el-card class="query-card">
      <div class="query-bar">
        <div class="query-row">
          <div class="query-item">
            <label>选择设备</label>
            <el-select
              v-model="selectedDevice"
              placeholder="选择设备"
              @change="loadData"
              style="width: 200px"
            >
              <el-option
                v-for="device in devices"
                :key="device.id"
                :label="`${device.name} (${device.mn})`"
                :value="device.mn"
              />
            </el-select>
          </div>

          <div class="query-item">
            <label>时间范围</label>
            <div class="time-selector">
              <el-radio-group v-model="timePreset" @change="handleTimePresetChange" size="small">
                <el-radio-button
                  v-for="preset in timePresets"
                  :key="preset.value"
                  :value="preset.value"
                >
                  {{ preset.label }}
                </el-radio-button>
              </el-radio-group>
            </div>
          </div>

          <div class="query-item" v-if="timePreset === 'custom'">
            <label>自定义时间</label>
            <el-date-picker
              v-model="dateRange"
              type="datetimerange"
              range-separator="至"
              start-placeholder="开始时间"
              end-placeholder="结束时间"
              @change="handleDateRangeChange"
              style="width: 360px"
            />
          </div>
        </div>

        <div class="query-row">
          <div class="query-item pollutant-selector">
            <label>选择污染物（可多选对比）</label>
            <el-select
              v-model="selectedPollutants"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="选择要对比的污染物"
              @change="handlePollutantChange"
              style="width: 400px"
            >
              <el-option-group
                v-for="group in groupedPollutantOptions"
                :key="group.label"
                :label="group.label"
              >
                <el-option
                  v-for="option in group.options"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                  :disabled="!availablePollutants.includes(option.value) && availablePollutants.length > 0"
                >
                  <span>{{ option.label }}</span>
                  <span v-if="!availablePollutants.includes(option.value) && availablePollutants.length > 0" class="no-data-hint">
                    (无数据)
                  </span>
                </el-option>
              </el-option-group>
            </el-select>
          </div>

          <div class="query-actions">
            <el-button type="primary" @click="loadData" :loading="loading">
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
        </div>
      </div>
    </el-card>

    <!-- 统计摘要卡片 -->
    <div class="stats-grid" v-if="statistics && statistics.length > 0">
      <el-card
        v-for="stat in statistics"
        :key="stat.code"
        class="stat-card"
        :style="{ '--stat-color': getPollutantColor(stat.code, statistics.indexOf(stat)) }"
      >
        <div class="stat-header">
          <span class="stat-name">{{ stat.name }}</span>
          <el-tag size="small" round>{{ stat.code }}</el-tag>
        </div>
        <div class="stat-body">
          <div class="stat-item">
            <span class="stat-label">最新值</span>
            <span class="stat-value latest">{{ formatPollutantValue(stat.code, stat.latest) }}</span>
            <span class="stat-unit">{{ stat.unit }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">平均值</span>
            <span class="stat-value">{{ formatPollutantValue(stat.code, stat.avg) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">最小值</span>
            <span class="stat-value">{{ formatPollutantValue(stat.code, stat.min) }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">最大值</span>
            <span class="stat-value">{{ formatPollutantValue(stat.code, stat.max) }}</span>
          </div>
        </div>
        <div class="stat-footer">
          <span>数据量: {{ stat.count }} 条</span>
          <span v-if="stat.exceedCount > 0" class="exceed-count">
            异常: {{ stat.exceedCount }} 次
          </span>
        </div>
      </el-card>

      <!-- 数据完整率卡片 -->
      <el-card class="stat-card completeness-card" v-if="dataCompleteness">
        <div class="stat-header">
          <span class="stat-name">数据完整率</span>
        </div>
        <div class="completeness-body">
          <el-progress
            type="dashboard"
            :percentage="Math.round(dataCompleteness.rate)"
            :color="dataCompleteness.rate >= 90 ? '#34C759' : dataCompleteness.rate >= 70 ? '#FF9500' : '#FF3B30'"
            :stroke-width="8"
          />
        </div>
        <div class="stat-footer">
          <span>{{ dataCompleteness.actual }} / {{ dataCompleteness.expected }} 条</span>
        </div>
      </el-card>
    </div>

    <!-- 趋势图卡片 -->
    <el-card class="chart-card">
      <div id="data-chart" style="height: 400px"></div>
      <div v-if="selectedPollutants.length === 0" class="chart-empty">
        <el-empty description="请选择要对比的污染物指标" />
      </div>
    </el-card>

    <!-- 数据明细表格 -->
    <el-card class="table-card">
      <template #header>
        <div class="table-header">
          <span>数据明细 (共 {{ data.filter(d => selectedPollutants.includes(d.pollutant_code)).length }} 条)</span>
        </div>
      </template>
      <el-table
        :data="data.filter(d => selectedPollutants.includes(d.pollutant_code))"
        v-loading="loading"
        stripe
        max-height="400"
      >
        <el-table-column prop="ts" label="时间" width="180" sortable>
          <template #default="{ row }">
            {{ new Date(row.ts).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
        <el-table-column prop="pollutant_code" label="污染物" width="180">
          <template #default="{ row }">
            <span>{{ getPollutantName(row.pollutant_code) }}</span>
            <span class="code-hint">({{ row.pollutant_code }})</span>
          </template>
        </el-table-column>
        <el-table-column prop="value" label="监测值" width="150" sortable>
          <template #default="{ row }">
            <span class="value-cell">
              {{ formatPollutantValue(row.pollutant_code, row.value) }}
              <span class="unit">{{ getPollutantUnit(row.pollutant_code) }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="flag" label="标志" width="80">
          <template #default="{ row }">
            <el-tag :type="getFlagType(row.flag)" size="small" round>
              {{ row.flag }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="device_id" label="设备ID" width="180" />
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.data-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
}

/* 查询条件卡片 */
.query-card {
  border-radius: 12px;
}

.query-bar {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.query-row {
  display: flex;
  align-items: flex-end;
  gap: 24px;
  flex-wrap: wrap;
}

.query-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.query-item label {
  font-size: 13px;
  color: #86868B;
  font-weight: 500;
}

.query-item.pollutant-selector {
  flex: 1;
  min-width: 400px;
}

.time-selector {
  display: flex;
  gap: 8px;
}

.query-actions {
  display: flex;
  gap: 12px;
  margin-left: auto;
}

.no-data-hint {
  color: #c0c4cc;
  font-size: 12px;
  margin-left: 8px;
}

/* 统计摘要卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.stat-card {
  border-radius: 12px;
  border-left: 4px solid var(--stat-color, #007AFF);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.stat-name {
  font-size: 15px;
  font-weight: 600;
  color: #1D1D1F;
}

.stat-body {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.stat-label {
  font-size: 12px;
  color: #86868B;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: #1D1D1F;
}

.stat-value.latest {
  font-size: 24px;
  color: var(--stat-color, #007AFF);
}

.stat-unit {
  font-size: 12px;
  color: #86868B;
}

.stat-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
  font-size: 12px;
  color: #86868B;
  display: flex;
  justify-content: space-between;
}

.exceed-count {
  color: #FF3B30;
  font-weight: 500;
}

/* 数据完整率卡片 */
.completeness-card {
  border-left-color: #34C759 !important;
}

.completeness-body {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}

/* 图表卡片 */
.chart-card {
  border-radius: 12px;
  position: relative;
}

.chart-empty {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

/* 表格卡片 */
.table-card {
  border-radius: 12px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.code-hint {
  color: #86868B;
  font-size: 12px;
  margin-left: 4px;
}

.value-cell {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.value-cell .unit {
  color: #86868B;
  font-size: 12px;
}

/* 按钮样式 */
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

:deep(.el-button--default),
:deep(.el-dropdown .el-button) {
  border-color: #dcdfe6 !important;
  color: #606266 !important;
  background-color: #fff !important;
}

:deep(.el-button--default:hover),
:deep(.el-dropdown .el-button:hover) {
  border-color: #0B1727 !important;
  color: #0B1727 !important;
  background-color: rgba(11, 23, 39, 0.06) !important;
}

/* Radio 按钮组样式 */
:deep(.el-radio-group) {
  flex-wrap: nowrap;
}

:deep(.el-radio-button__inner) {
  border-color: #dcdfe6 !important;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
  box-shadow: -1px 0 0 0 #0B1727 !important;
}

/* 响应式 */
@media (max-width: 768px) {
  .query-row {
    flex-direction: column;
    align-items: stretch;
  }

  .query-item.pollutant-selector {
    min-width: 100%;
  }

  .query-actions {
    margin-left: 0;
    justify-content: flex-end;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }
}
</style>
