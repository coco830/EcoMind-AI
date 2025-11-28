<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { dashboardApi, type DashboardStats, type TrendParams } from '@/api/dashboard'
import { deviceApi, type Device } from '@/api/devices'
import { aiApi, type PredictionResponse } from '@/api/ai'
import type { MonitoringData } from '@/api/data'
import * as echarts from 'echarts'
import DeviceMap from '@/components/DeviceMap.vue'
import AiAnalysisCard from '@/components/AiAnalysisCard.vue'

// Import pollutant library
import {
  POLLUTANT_MAP,
  getPollutantName,
  getPollutantUnit,
  getPollutantInfo,
  formatPollutantValue,
  generateGroupedPollutantOptions,
  getPollutantColor,
  isHeavyMetal,
  COMMON_POLLUTANTS,
  HEAVY_METAL_POLLUTANTS,
} from '@/config/pollutants'

// Dashboard stats
const stats = ref<DashboardStats>({
  device_count: 0,
  online_count: 0,
  offline_count: 0,
  alarm_count: 0,
  data_count: 0,
  pending_alarms: 0
})

// Devices for map
const devices = ref<Device[]>([])

// Monitoring data for charts
const trendData = ref<MonitoringData[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

// Prediction data
const predictionData = ref<PredictionResponse | null>(null)
const selectedDeviceForPrediction = ref<string>('')
const predictionLoading = ref(false)

// Demo data injection
const demoInjectLoading = ref(false)

// ECharts instance
let trendChart: echarts.ECharts | null = null

// Active pollutants for the selected device (dynamic from actual data)
const activePollutants = ref<string[]>([])

// Latest values for real-time monitoring cards
const latestValues = ref<Record<string, { value: number; flag: string; ts: string }>>({})

// Whether to show only device's actual data or use presets
const showActualDataOnly = ref(true)

// Generate grouped pollutant options (by category)
const groupedPollutantOptions = computed(() => generateGroupedPollutantOptions())

// Quick filter presets - 行业快捷预设
// 注：电镀行业重金属已包含在"重金属"分类中
const pollutantPresets = [
  { label: '设备实际', value: 'actual', codes: [], hasSubmenu: false },
  { label: '常用指标', value: 'common', codes: COMMON_POLLUTANTS, hasSubmenu: false },
  {
    label: '重金属',
    value: 'heavy_metals',
    codes: HEAVY_METAL_POLLUTANTS,
    hasSubmenu: true,
    submenu: [
      { label: '一类 (5)', value: 'class1', filter: 'heavy_metals_class1' },
      { label: '二类 (18)', value: 'class2', filter: 'heavy_metals_class2' },
      { label: '全部 (23)', value: 'all', filter: null },
    ]
  },
]
const selectedPreset = ref('actual')  // 默认显示设备实际数据
const heavyMetalFilter = ref<string | null>(null)  // 重金属子分类筛选

// 展开/收起状态
const isExpanded = ref(false)
const defaultVisibleCount = 8  // 默认显示数量

// Selected pollutant for trend chart
const selectedPollutant = ref<string>('w01018')

// Current pollutant metadata
const currentPollutantMeta = computed(() => {
  const info = getPollutantInfo(selectedPollutant.value)
  return {
    label: info?.name || selectedPollutant.value,
    unit: info?.unit || 'mg/L',
    precision: info?.precision || 2
  }
})

// Selected device name for AI analysis
const selectedDeviceName = computed(() => {
  const device = devices.value.find(d => d.mn === selectedDeviceForPrediction.value)
  return device?.name || selectedDeviceForPrediction.value
})

// 过滤后的活跃污染物（支持重金属子分类筛选）
const filteredActivePollutants = computed(() => {
  let pollutants = activePollutants.value

  // 如果选择了重金属预设且有子分类筛选
  if (selectedPreset.value === 'heavy_metals' && heavyMetalFilter.value) {
    pollutants = pollutants.filter(code => {
      const info = getPollutantInfo(code)
      return info?.category === heavyMetalFilter.value
    })
  }

  return pollutants
})

// 可见的污染物数量
const visiblePollutantCount = computed(() => {
  return isExpanded.value ? filteredActivePollutants.value.length : defaultVisibleCount
})

// 是否显示展开按钮
const showExpandButton = computed(() => {
  return filteredActivePollutants.value.length > defaultVisibleCount
})

// 剩余未显示数量
const remainingCount = computed(() => {
  return Math.max(0, filteredActivePollutants.value.length - defaultVisibleCount)
})

// Real-time monitoring cards data
const monitoringCards = computed(() => {
  return filteredActivePollutants.value
    .slice(0, visiblePollutantCount.value)
    .map((code, index) => {
      const info = getPollutantInfo(code)
      const latest = latestValues.value[code]
      const color = getPollutantColor(code, index)

      return {
        code,
        name: info?.name || code,
        unit: info?.unit || 'mg/L',
        precision: info?.precision || 2,
        value: latest?.value,
        flag: latest?.flag || 'N',
        timestamp: latest?.ts,
        color,
        isHeavyMetal: isHeavyMetal(code)
      }
    })
})

// Helper function to format datetime
const formatDateTime = (date: Date): string => {
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${month}/${day} ${hours}:${minutes}`
}

// Group data by pollutant code
const groupedData = computed(() => {
  const groups: Record<string, MonitoringData[]> = {}
  for (const item of trendData.value) {
    if (!groups[item.pollutant_code]) {
      groups[item.pollutant_code] = []
    }
    groups[item.pollutant_code].push(item)
  }
  return groups
})

// Load dashboard data
const loadData = async () => {
  loading.value = true
  error.value = null

  try {
    const [statsData, deviceList] = await Promise.all([
      dashboardApi.getStats(),
      deviceApi.list()
    ])

    stats.value = statsData
    devices.value = deviceList

    // Auto-select first device
    if (!selectedDeviceForPrediction.value && deviceList.length > 0) {
      selectedDeviceForPrediction.value = deviceList[0].mn
      // Parse device's active pollutants if available
      parseDevicePollutants(deviceList[0])
    }

    // If in "actual" mode (default), load device pollutants from actual data
    if (showActualDataOnly.value && selectedDeviceForPrediction.value) {
      await loadDevicePollutants()
    }

    await refreshTrendAndPrediction()
  } catch (e: unknown) {
    console.error('Failed to load dashboard data:', e)
    error.value = e instanceof Error ? e.message : '加载数据失败'
  } finally {
    loading.value = false
  }
}

// Parse device's pollutant configuration
const parseDevicePollutants = (device: Device) => {
  if (device.pollutant_codes) {
    let codes: string[] = []
    if (Array.isArray(device.pollutant_codes)) {
      codes = device.pollutant_codes
    } else if (typeof device.pollutant_codes === 'string') {
      try {
        codes = JSON.parse(device.pollutant_codes)
      } catch {
        codes = device.pollutant_codes.split(',').map(s => s.trim())
      }
    }
    if (codes.length > 0) {
      activePollutants.value = codes.filter(c => POLLUTANT_MAP[c.toLowerCase()])
    }
  }
}

// Load trend data
const loadTrend = async () => {
  try {
    const params: TrendParams = {
      pollutant_code: selectedPollutant.value,
      hours: 24,
      limit: 200
    }
    if (selectedDeviceForPrediction.value) {
      params.device_id = selectedDeviceForPrediction.value
    }
    const trend = await dashboardApi.getTrend(params)
    trendData.value = trend

    // Update latest values from trend data
    updateLatestValues(trend)

    updateChart()
  } catch (e) {
    console.error('Failed to load trend data:', e)
  }
}

// Update latest values for monitoring cards
const updateLatestValues = (data: MonitoringData[]) => {
  const latest: Record<string, { value: number; flag: string; ts: string }> = {}

  for (const item of data) {
    const code = item.pollutant_code
    if (!latest[code] || new Date(item.ts) > new Date(latest[code].ts)) {
      latest[code] = {
        value: item.value,
        flag: item.flag || 'N',
        ts: item.ts
      }
    }
  }

  latestValues.value = { ...latestValues.value, ...latest }
}

// Load all pollutants for the selected device (for "设备实际" mode)
const loadDevicePollutants = async () => {
  if (!selectedDeviceForPrediction.value) return

  try {
    const data = await dashboardApi.getDevicePollutants(selectedDeviceForPrediction.value, 24)

    if (data.length > 0) {
      // Extract unique pollutant codes from actual device data
      const detectedCodes = data.map(item => item.pollutant_code)
      activePollutants.value = detectedCodes

      // Update latest values
      updateLatestValues(data)

      console.log(`Detected ${detectedCodes.length} pollutants from device data:`, detectedCodes)
    } else {
      console.log('No data found for device, falling back to common pollutants')
      activePollutants.value = COMMON_POLLUTANTS
    }
  } catch (e) {
    console.error('Failed to load device pollutants:', e)
    // Fallback to common pollutants
    activePollutants.value = COMMON_POLLUTANTS
  }
}

// Load prediction
const loadPrediction = async () => {
  if (!selectedDeviceForPrediction.value) return

  predictionLoading.value = true
  try {
    const prediction = await aiApi.predict(selectedDeviceForPrediction.value, {
      pollutant_code: selectedPollutant.value,
      hours: 24,
      prediction_hours: 4
    })
    predictionData.value = prediction
    updateChart()
  } catch (e: unknown) {
    console.error('Failed to load prediction:', e)
  } finally {
    predictionLoading.value = false
  }
}

// Event handlers
const onDeviceChange = async () => {
  const device = devices.value.find(d => d.mn === selectedDeviceForPrediction.value)
  if (device) {
    parseDevicePollutants(device)
  }

  // If in "actual" mode, reload device pollutants for the new device
  if (showActualDataOnly.value) {
    await loadDevicePollutants()
  }

  await refreshTrendAndPrediction()
}

const onPollutantChange = async () => {
  await refreshTrendAndPrediction()
}

const onPresetChange = async (presetValue?: string) => {
  const value = presetValue || selectedPreset.value
  selectedPreset.value = value
  const preset = pollutantPresets.find(p => p.value === value)

  // 重置展开状态和子分类筛选
  isExpanded.value = false
  heavyMetalFilter.value = null

  if (preset) {
    if (preset.value === 'actual') {
      // 设备实际模式：从设备实际上报数据中检测所有污染物
      showActualDataOnly.value = true
      await loadDevicePollutants()
      await refreshTrendAndPrediction()
    } else {
      // 预设模式：使用固定列表
      showActualDataOnly.value = false
      activePollutants.value = preset.codes
      // Set first pollutant as selected
      if (preset.codes.length > 0 && !preset.codes.includes(selectedPollutant.value)) {
        selectedPollutant.value = preset.codes[0]
        refreshTrendAndPrediction()
      }
    }
  }
}

// 重金属子分类筛选
const onHeavyMetalFilterChange = (filter: string | null) => {
  heavyMetalFilter.value = filter
  isExpanded.value = false  // 切换分类时收起
}

// 展开/收起切换
const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const refreshTrendAndPrediction = async () => {
  await Promise.all([loadTrend(), loadPrediction()])
}

// Inject demo data for testing
const injectDemoData = async () => {
  if (!selectedDeviceForPrediction.value) {
    ElMessage.warning('请先选择设备')
    return
  }

  demoInjectLoading.value = true
  try {
    const result = await dashboardApi.injectDemoData({
      device_id: selectedDeviceForPrediction.value,
      hours: 24,
      interval_minutes: 15,
      include_anomalies: true,
    })

    ElMessage.success(`${result.message}（${result.pollutants} 种污染物，${result.data_points} 个数据点）`)

    // Refresh data after injection
    await loadData()
  } catch (e: unknown) {
    console.error('Failed to inject demo data:', e)
    ElMessage.error(e instanceof Error ? e.message : '注入演示数据失败')
  } finally {
    demoInjectLoading.value = false
  }
}

const handleDeviceClick = (device: Device) => {
  selectedDeviceForPrediction.value = device.mn
  parseDevicePollutants(device)
  refreshTrendAndPrediction()
}

// Update chart with dynamic Y-axis (scale: true for auto-scaling)
const updateChart = () => {
  if (!trendChart) return

  const timestamps = [...new Set(trendData.value.map(d => d.ts))].sort()
  const times = timestamps.map(t => formatDateTime(new Date(t)))

  const series: echarts.SeriesOption[] = []
  const legendData: string[] = []

  for (const [code, data] of Object.entries(groupedData.value)) {
    const name = getPollutantName(code)
    legendData.push(name)

    const valueMap = new Map(data.map(d => [d.ts, d.value]))
    const values = timestamps.map(ts => valueMap.get(ts) ?? null)

    series.push({
      name,
      type: 'line',
      smooth: true,
      data: values,
      areaStyle: { opacity: 0.1 },
      emphasis: { focus: 'series' }
    })
  }

  // Add prediction data if available
  if (predictionData.value && predictionData.value.predictions.length > 0) {
    const prediction = predictionData.value
    const historicalTimes = prediction.historical_data.map(h => formatDateTime(new Date(h.timestamp)))
    const predictionTimes = prediction.predictions.map(p => formatDateTime(new Date(p.timestamp)))
    const allTimes = [...historicalTimes, ...predictionTimes]

    const pollutantLabel = currentPollutantMeta.value.label
    const valueUnit = currentPollutantMeta.value.unit
    const historicalName = `${pollutantLabel} (历史)`
    const historicalValues: (number | null)[] = []

    const histMap = new Map(
      prediction.historical_data.map(h => [
        formatDateTime(new Date(h.timestamp)),
        h.value
      ])
    )

    for (const t of allTimes) {
      historicalValues.push(histMap.get(t) ?? null)
    }

    const predictionName = `${pollutantLabel} (预测)`
    const predictionValues: (number | null)[] = []
    const predictionLowerValues: (number | null)[] = []
    const predictionUpperValues: (number | null)[] = []

    const predMap = new Map(
      prediction.predictions.map(p => [
        formatDateTime(new Date(p.timestamp)),
        { value: p.value, lower: p.value_lower, upper: p.value_upper }
      ])
    )

    for (const t of allTimes) {
      const pred = predMap.get(t)
      predictionValues.push(pred?.value ?? null)
      predictionLowerValues.push(pred?.lower ?? null)
      predictionUpperValues.push(pred?.upper ?? null)
    }

    // Connect prediction to last historical point
    if (historicalValues.length > 0 && predictionValues.length > 0) {
      const lastHistIdx = historicalValues.map((v, i) => v !== null ? i : -1).filter(i => i >= 0).pop()
      if (lastHistIdx !== undefined && lastHistIdx >= 0) {
        const firstPredIdx = predictionValues.findIndex(v => v !== null)
        if (firstPredIdx > 0) {
          predictionValues[lastHistIdx] = historicalValues[lastHistIdx]
        }
      }
    }

    series.length = 0
    legendData.length = 0

    const mainColor = getPollutantColor(selectedPollutant.value)

    legendData.push(historicalName)
    series.push({
      name: historicalName,
      type: 'line',
      smooth: true,
      data: historicalValues,
      lineStyle: { width: 2 },
      areaStyle: { opacity: 0.1, color: mainColor },
      itemStyle: { color: mainColor },
      emphasis: { focus: 'series' },
      z: 10
    })

    const confidenceLowerName = '置信下限'
    legendData.push(confidenceLowerName)
    series.push({
      name: confidenceLowerName,
      type: 'line',
      smooth: true,
      data: predictionLowerValues,
      lineStyle: { opacity: 0 },
      areaStyle: { opacity: 0 },
      itemStyle: { opacity: 0 },
      stack: 'confidence',
      symbol: 'none',
      z: 1
    })

    const confidenceBandName = '80%置信区间'
    legendData.push(confidenceBandName)
    const bandValues = predictionUpperValues.map((upper, i) => {
      const lower = predictionLowerValues[i]
      if (upper !== null && lower !== null) {
        return upper - lower
      }
      return null
    })
    series.push({
      name: confidenceBandName,
      type: 'line',
      smooth: true,
      data: bandValues,
      lineStyle: { opacity: 0 },
      areaStyle: {
        opacity: 0.3,
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(103, 194, 58, 0.4)' },
            { offset: 1, color: 'rgba(103, 194, 58, 0.1)' }
          ]
        }
      },
      itemStyle: { opacity: 0 },
      stack: 'confidence',
      symbol: 'none',
      z: 2
    })

    legendData.push(predictionName)
    series.push({
      name: predictionName,
      type: 'line',
      smooth: true,
      data: predictionValues,
      lineStyle: { width: 2, type: 'dashed' },
      itemStyle: { color: '#67c23a' },
      emphasis: { focus: 'series' },
      z: 20
    })

    const yAxisName = `${pollutantLabel} (${valueUnit})`

    trendChart.setOption({
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        formatter: (params: any) => {
          if (!Array.isArray(params)) return ''
          let result = `<div style="font-weight:bold">${params[0].axisValue}</div>`

          for (const p of params) {
            if (p.value !== null && p.value !== undefined) {
              if (p.seriesName === confidenceLowerName || p.seriesName === confidenceBandName) {
                continue
              }

              const isPrediction = p.seriesName.includes('预测')
              const marker = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${p.color};margin-right:5px;"></span>`
              const formattedValue = formatPollutantValue(selectedPollutant.value, p.value)
              result += `<div>${marker}${p.seriesName}: ${formattedValue} ${valueUnit}${isPrediction ? ' (AI预测)' : ''}</div>`

              if (isPrediction) {
                const timeKey = params[0].axisValue
                const pred = predMap.get(timeKey)
                if (pred) {
                  const lowerFormatted = formatPollutantValue(selectedPollutant.value, pred.lower)
                  const upperFormatted = formatPollutantValue(selectedPollutant.value, pred.upper)
                  result += `<div style="color:#67c23a;font-size:11px;margin-left:15px;">80%置信区间: [${lowerFormatted}, ${upperFormatted}]</div>`
                }
              }
            }
          }
          return result
        }
      },
      legend: {
        data: [historicalName, predictionName, confidenceBandName],
        bottom: 0,
        selected: { [confidenceLowerName]: false }
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '15%',
        top: '10%',
        containLabel: true
      },
      xAxis: {
        type: 'category',
        data: allTimes,
        axisLabel: { rotate: 45, fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        name: yAxisName,
        scale: true, // IMPORTANT: Auto-scale for small values (heavy metals)
        min: (value: { min: number }) => {
          // Add 10% padding below min value, ensure non-negative
          const padding = Math.abs(value.min) * 0.1
          return Math.max(0, value.min - padding)
        },
        max: (value: { max: number }) => {
          // Add 10% padding above max value
          const padding = Math.abs(value.max) * 0.1
          return value.max + padding
        },
        splitNumber: 5, // Ensure reasonable number of ticks
        axisLabel: {
          fontSize: 10,
          formatter: (value: number) => formatPollutantValue(selectedPollutant.value, value)
        }
      },
      series
    }, true)

    return
  }

  // No prediction data
  if (series.length === 0) {
    series.push({
      name: '暂无数据',
      type: 'line',
      data: []
    })
  }

  trendChart.setOption({
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        if (!Array.isArray(params)) return ''
        let result = `<div style="font-weight:bold">${params[0].axisValue}</div>`
        for (const p of params) {
          if (p.value !== null && p.value !== undefined) {
            const code = Object.keys(groupedData.value).find(k => getPollutantName(k) === p.seriesName)
            const formattedValue = code ? formatPollutantValue(code, p.value) : p.value.toFixed(2)
            const unit = code ? getPollutantUnit(code) : 'mg/L'
            const marker = `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${p.color};margin-right:5px;"></span>`
            result += `<div>${marker}${p.seriesName}: ${formattedValue} ${unit}</div>`
          }
        }
        return result
      }
    },
    legend: {
      data: legendData,
      bottom: 0
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '15%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: times,
      axisLabel: { rotate: 45, fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      name: `${currentPollutantMeta.value.label} (${currentPollutantMeta.value.unit})`,
      scale: true, // IMPORTANT: Auto-scale
      min: (value: { min: number }) => {
        // Add 10% padding below min value, ensure non-negative
        const padding = Math.abs(value.min) * 0.1
        return Math.max(0, value.min - padding)
      },
      max: (value: { max: number }) => {
        // Add 10% padding above max value
        const padding = Math.abs(value.max) * 0.1
        return value.max + padding
      },
      splitNumber: 5,
      axisLabel: {
        fontSize: 10,
        formatter: (value: number) => formatPollutantValue(selectedPollutant.value, value)
      }
    },
    series
  }, true)
}

const initChart = () => {
  const chartDom = document.getElementById('trend-chart')
  if (chartDom) {
    trendChart = echarts.init(chartDom)
    window.addEventListener('resize', () => trendChart?.resize())
  }
}

let refreshInterval: number

onMounted(() => {
  initChart()
  loadData()
  refreshInterval = window.setInterval(loadData, 30000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
  if (trendChart) {
    window.removeEventListener('resize', () => trendChart?.resize())
    trendChart.dispose()
  }
})
</script>

<template>
  <div class="dashboard">
    <!-- Error message -->
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      show-icon
      closable
      @close="error = null"
      class="error-alert"
    />

    <!-- Stats cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #409eff">
              <el-icon size="32"><Monitor /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.device_count }}</div>
              <div class="stat-label">设备总数</div>
            </div>
          </div>
          <div class="stat-footer">
            <span class="online">在线: {{ stats.online_count }}</span>
            <span class="offline">离线: {{ stats.offline_count }}</span>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #67c23a">
              <el-icon size="32"><DataLine /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ trendData.length }}</div>
              <div class="stat-label">数据点数</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6a23c">
              <el-icon size="32"><Bell /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.pending_alarms }}</div>
              <div class="stat-label">待处理告警</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f56c6c">
              <el-icon size="32"><WarningFilled /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ stats.alarm_count }}</div>
              <div class="stat-label">异常设备</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Real-time Monitoring Cards (Dynamic) -->
    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <el-card class="monitoring-card">
          <template #header>
            <div class="card-header">
              <span>实时监测数据</span>
              <div class="header-right">
                <!-- 演示数据注入按钮 -->
                <el-button
                  type="warning"
                  size="small"
                  :loading="demoInjectLoading"
                  @click="injectDemoData"
                  class="demo-inject-btn"
                >
                  <el-icon v-if="!demoInjectLoading"><Upload /></el-icon>
                  注入演示数据
                </el-button>
                <el-divider direction="vertical" />
                <div class="preset-buttons">
                  <template v-for="preset in pollutantPresets" :key="preset.value">
                    <!-- 带下拉菜单的按钮（重金属） -->
                    <el-dropdown
                      v-if="preset.hasSubmenu"
                      trigger="click"
                      @command="(cmd: string) => { onPresetChange(preset.value); onHeavyMetalFilterChange(cmd === 'all' ? null : cmd === 'class1' ? 'heavy_metals_class1' : 'heavy_metals_class2'); }"
                    >
                      <el-button
                        :type="selectedPreset === preset.value ? 'primary' : 'default'"
                        size="small"
                        class="preset-dropdown-btn"
                      >
                        {{ preset.label }}
                        <el-icon class="el-icon--right"><ArrowDown /></el-icon>
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item
                            v-for="sub in preset.submenu"
                            :key="sub.value"
                            :command="sub.value"
                          >
                            <span :class="{ 'active-filter': selectedPreset === preset.value && (sub.filter === heavyMetalFilter || (sub.value === 'all' && !heavyMetalFilter)) }">
                              {{ sub.label }}
                            </span>
                          </el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                    <!-- 普通按钮 -->
                    <el-button
                      v-else
                      :type="selectedPreset === preset.value ? 'primary' : 'default'"
                      size="small"
                      @click="onPresetChange(preset.value)"
                    >
                      {{ preset.label }}
                    </el-button>
                  </template>
                </div>
              </div>
            </div>
            <!-- 重金属子分类标签（选中重金属预设时显示） -->
            <div v-if="selectedPreset === 'heavy_metals'" class="sub-filter-tags">
              <el-tag
                v-for="sub in pollutantPresets.find(p => p.value === 'heavy_metals')?.submenu"
                :key="sub.value"
                :type="(sub.filter === heavyMetalFilter || (sub.value === 'all' && !heavyMetalFilter)) ? '' : 'info'"
                :effect="(sub.filter === heavyMetalFilter || (sub.value === 'all' && !heavyMetalFilter)) ? 'dark' : 'plain'"
                class="sub-tag"
                @click="onHeavyMetalFilterChange(sub.value === 'all' ? null : sub.filter)"
              >
                {{ sub.label }}
              </el-tag>
              <span class="filter-hint">
                当前显示 {{ filteredActivePollutants.length }} 项
              </span>
            </div>
          </template>
          <!-- 有数据时显示卡片 -->
          <el-row v-if="monitoringCards.length > 0" :gutter="16">
            <el-col
              v-for="card in monitoringCards"
              :key="card.code"
              :span="6"
              :xs="12"
              :sm="8"
              :md="6"
            >
              <div
                class="pollutant-card"
                :class="{ 'heavy-metal': card.isHeavyMetal }"
                :style="{ borderLeftColor: card.color }"
              >
                <div class="pollutant-header">
                  <span class="pollutant-name">{{ card.name }}</span>
                  <el-tag
                    :type="card.flag === 'N' ? 'success' : 'warning'"
                    size="small"
                    class="flag-tag"
                  >
                    {{ card.flag }}
                  </el-tag>
                </div>
                <div class="pollutant-value" :style="{ color: card.color }">
                  <template v-if="card.value !== undefined">
                    {{ card.value.toFixed(card.precision) }}
                  </template>
                  <template v-else>
                    --
                  </template>
                  <span class="pollutant-unit">{{ card.unit }}</span>
                </div>
                <div class="pollutant-code">{{ card.code }}</div>
              </div>
            </el-col>
          </el-row>
          <!-- 展开/收起按钮 -->
          <div v-if="showExpandButton" class="expand-button-container">
            <el-button
              type="primary"
              link
              @click="toggleExpand"
              class="expand-btn"
            >
              <template v-if="isExpanded">
                <el-icon><ArrowUp /></el-icon>
                收起
              </template>
              <template v-else>
                <el-icon><ArrowDown /></el-icon>
                展开更多 ({{ remainingCount }})
              </template>
            </el-button>
          </div>
          <!-- 无数据时显示提示 -->
          <div v-else-if="monitoringCards.length === 0" class="no-data-hint">
            <el-empty description="暂无监测数据">
              <template #description>
                <p>当前设备尚未上报数据</p>
                <p class="hint-text">数据将在设备数采仪上报后自动显示</p>
              </template>
            </el-empty>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Device Map -->
    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <el-card class="map-card">
          <template #header>
            <div class="card-header">
              <span>设备分布地图</span>
              <el-tag type="info" size="small">{{ devices.length }} 台设备</el-tag>
            </div>
          </template>
          <DeviceMap
            :devices="devices"
            :loading="loading"
            height="400px"
            @device-click="handleDeviceClick"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- Charts -->
    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">
              <div class="header-left">
                <span>{{ currentPollutantMeta.label }} 实时趋势 + AI预测</span>
                <el-tag v-if="predictionData?.model_type" type="success" size="small" class="model-tag">
                  {{
                    predictionData.model_type === 'prophet'
                      ? 'Prophet预测'
                      : predictionData.model_type === 'neuralprophet'
                        ? 'NeuralProphet预测'
                        : predictionData.model_type === 'simple_average'
                          ? '朴素预测'
                          : '数据不足'
                  }}
                </el-tag>
              </div>
              <div class="header-right">
                <el-select
                  v-model="selectedDeviceForPrediction"
                  placeholder="选择设备"
                  size="small"
                  style="width: 180px; margin-right: 10px;"
                  @change="onDeviceChange"
                  :loading="predictionLoading"
                >
                  <el-option
                    v-for="device in devices"
                    :key="device.id"
                    :label="device.name || device.mn"
                    :value="device.mn"
                  />
                </el-select>
                <el-select
                  v-model="selectedPollutant"
                  placeholder="监测因子"
                  size="small"
                  style="width: 200px; margin-right: 10px;"
                  @change="onPollutantChange"
                  filterable
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
                    />
                  </el-option-group>
                </el-select>
                <el-button
                  type="primary"
                  :icon="Refresh"
                  circle
                  size="small"
                  @click="loadData"
                  :loading="loading"
                />
              </div>
            </div>
          </template>
          <div id="trend-chart" style="height: 400px"></div>
          <div v-if="predictionData && predictionData.predictions.length > 0" class="prediction-info">
            <el-tag type="info" size="small">
              预测时间范围: 未来 {{ predictionData.predictions.length * 15 }} 分钟
            </el-tag>
            <el-tag v-if="predictionData.metrics?.interval_width" type="success" size="small">
              置信区间: {{ (predictionData.metrics.interval_width * 100).toFixed(0) }}%
            </el-tag>
            <el-tag v-if="predictionData.metrics?.data_points" type="warning" size="small">
              训练数据: {{ predictionData.metrics.data_points }} 点
            </el-tag>
          </div>
          <div v-if="trendData.length === 0 && !loading" class="no-data">
            暂无监测数据
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- AI Analysis Card - Comprehensive Analysis Mode (analyzes all pollutants) -->
    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <AiAnalysisCard
          :device-id="selectedDeviceForPrediction"
          :device-name="selectedDeviceName"
        />
        <!-- Note: Not passing pollutant prop enables comprehensive analysis of ALL pollutants -->
      </el-col>
    </el-row>

    <!-- Data table -->
    <el-row :gutter="20" class="content-row">
      <el-col :span="24">
        <el-card class="data-card">
          <template #header>
            <span>最新监测数据</span>
          </template>
          <el-table :data="trendData.slice(0, 10)" style="width: 100%" size="small">
            <el-table-column prop="device_id" label="设备ID" width="150" />
            <el-table-column prop="pollutant_code" label="污染物" width="150">
              <template #default="{ row }">
                <span>{{ getPollutantName(row.pollutant_code) }}</span>
                <span class="code-hint">({{ row.pollutant_code }})</span>
              </template>
            </el-table-column>
            <el-table-column prop="value" label="监测值" width="140">
              <template #default="{ row }">
                <span :class="{ 'heavy-metal-value': isHeavyMetal(row.pollutant_code) }">
                  {{ formatPollutantValue(row.pollutant_code, row.value) }}
                  <span class="value-unit">{{ getPollutantUnit(row.pollutant_code) }}</span>
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="flag" label="标记" width="80">
              <template #default="{ row }">
                <el-tag :type="row.flag === 'N' ? 'success' : 'warning'" size="small">
                  {{ row.flag }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ts" label="时间">
              <template #default="{ row }">
                {{ new Date(row.ts).toLocaleString('zh-CN') }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script lang="ts">
import { Refresh, ArrowDown, ArrowUp, Upload } from '@element-plus/icons-vue'
export default {
  components: { Refresh, ArrowDown, ArrowUp, Upload }
}
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.error-alert {
  margin-bottom: 20px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  .stat-content {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .stat-icon {
    width: 64px;
    height: 64px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
  }

  .stat-value {
    font-size: 28px;
    font-weight: bold;
    color: #333;
  }

  .stat-label {
    color: #999;
    font-size: 14px;
  }

  .stat-footer {
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid #eee;
    display: flex;
    gap: 16px;
    font-size: 12px;

    .online {
      color: #67c23a;
    }

    .offline {
      color: #909399;
    }
  }
}

.content-row {
  margin-bottom: 20px;
}

/* Real-time Monitoring Cards */
.monitoring-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .demo-inject-btn {
    .el-icon {
      margin-right: 4px;
    }
  }

  .preset-buttons {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .preset-dropdown-btn {
    .el-icon--right {
      margin-left: 4px;
    }
  }

  .sub-filter-tags {
    margin-top: 12px;
    display: flex;
    align-items: center;
    gap: 8px;

    .sub-tag {
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        transform: scale(1.05);
      }
    }

    .filter-hint {
      color: #909399;
      font-size: 12px;
      margin-left: 8px;
    }
  }
}

.active-filter {
  color: #409eff;
  font-weight: 500;
}

.expand-button-container {
  text-align: center;
  padding: 16px 0 8px;
  border-top: 1px dashed #eee;
  margin-top: 8px;

  .expand-btn {
    font-size: 14px;

    .el-icon {
      margin-right: 4px;
    }
  }
}

.pollutant-card {
  background: #fafafa;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  border-left: 4px solid #409eff;
  transition: all 0.3s;

  &:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    transform: translateY(-2px);
  }

  &.heavy-metal {
    background: linear-gradient(135deg, #f5f0ff 0%, #fff 100%);
  }

  .pollutant-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .pollutant-name {
    font-size: 14px;
    font-weight: 500;
    color: #333;
  }

  .flag-tag {
    font-size: 10px;
  }

  .pollutant-value {
    font-size: 24px;
    font-weight: bold;
    margin-bottom: 4px;
  }

  .pollutant-unit {
    font-size: 12px;
    font-weight: normal;
    color: #909399;
    margin-left: 4px;
  }

  .pollutant-code {
    font-size: 11px;
    color: #909399;
  }
}

.map-card {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}

.chart-card {
  min-height: 480px;

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .header-left {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .header-right {
      display: flex;
      align-items: center;
    }

    .model-tag {
      font-size: 11px;
    }
  }

  .prediction-info {
    display: flex;
    gap: 10px;
    padding: 10px 0;
    justify-content: center;
  }
}

.data-card {
  .code-hint {
    color: #909399;
    font-size: 11px;
    margin-left: 4px;
  }

  .heavy-metal-value {
    color: #8B5CF6;
  }

  .value-unit {
    margin-left: 4px;
    color: #909399;
    font-size: 12px;
  }
}

.no-data {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
  font-size: 14px;
}

.no-data-hint {
  padding: 40px 0;
  text-align: center;

  .hint-text {
    color: #909399;
    font-size: 12px;
    margin-top: 8px;
  }
}

:deep(.el-card__header) {
  padding: 12px 20px;
  border-bottom: 1px solid #eee;
}
</style>
