<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
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

// Router
const router = useRouter()

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

// Quick filter presets
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
const selectedPreset = ref('actual')
const heavyMetalFilter = ref<string | null>(null)

// Expand/collapse state
const isExpanded = ref(false)
const defaultVisibleCount = 8

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

// Filtered active pollutants
const filteredActivePollutants = computed(() => {
  let pollutants = activePollutants.value

  if (selectedPreset.value === 'heavy_metals' && heavyMetalFilter.value) {
    pollutants = pollutants.filter(code => {
      const info = getPollutantInfo(code)
      return info?.category === heavyMetalFilter.value
    })
  }

  return pollutants
})

// Visible pollutant count
const visiblePollutantCount = computed(() => {
  return isExpanded.value ? filteredActivePollutants.value.length : defaultVisibleCount
})

// Show expand button
const showExpandButton = computed(() => {
  return filteredActivePollutants.value.length > defaultVisibleCount
})

// Remaining count
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

    if (!selectedDeviceForPrediction.value && deviceList.length > 0) {
      selectedDeviceForPrediction.value = deviceList[0].mn
      parseDevicePollutants(deviceList[0])
    }

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
    const rawCodes = device.pollutant_codes
    if (Array.isArray(rawCodes)) {
      codes = rawCodes
    } else {
      // 处理可能的字符串类型（兼容旧数据）
      const codesStr = rawCodes as unknown as string
      if (typeof codesStr === 'string') {
        try {
          codes = JSON.parse(codesStr)
        } catch {
          codes = codesStr.split(',').map((s: string) => s.trim())
        }
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

// Load all pollutants for the selected device
const loadDevicePollutants = async () => {
  if (!selectedDeviceForPrediction.value) return

  try {
    const data = await dashboardApi.getDevicePollutants(selectedDeviceForPrediction.value, 24)

    if (data.length > 0) {
      const detectedCodes = data.map(item => item.pollutant_code)
      activePollutants.value = detectedCodes
      updateLatestValues(data)
    } else {
      activePollutants.value = COMMON_POLLUTANTS
    }
  } catch (e) {
    console.error('Failed to load device pollutants:', e)
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

  isExpanded.value = false
  heavyMetalFilter.value = null

  if (preset) {
    if (preset.value === 'actual') {
      showActualDataOnly.value = true
      await loadDevicePollutants()
      await refreshTrendAndPrediction()
    } else {
      showActualDataOnly.value = false
      activePollutants.value = preset.codes
      if (preset.codes.length > 0 && !preset.codes.includes(selectedPollutant.value)) {
        selectedPollutant.value = preset.codes[0]
        refreshTrendAndPrediction()
      }
    }
  }
}

const onHeavyMetalFilterChange = (filter: string | null) => {
  heavyMetalFilter.value = filter
  isExpanded.value = false
}

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const refreshTrendAndPrediction = async () => {
  await Promise.all([loadTrend(), loadPrediction()])
}

const handleDeviceClick = (device: Device) => {
  selectedDeviceForPrediction.value = device.mn
  parseDevicePollutants(device)
  refreshTrendAndPrediction()
}

// Apple-style ECharts configuration
const getAppleChartOptions = () => ({
  backgroundColor: 'transparent',
  textStyle: {
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '15%',
    top: '8%',
    containLabel: true
  },
  tooltip: {
    trigger: 'axis',
    backgroundColor: 'rgba(255, 255, 255, 0.96)',
    borderColor: 'transparent',
    borderRadius: 12,
    padding: [12, 16],
    boxShadow: '0 4px 24px rgba(0, 0, 0, 0.12)',
    textStyle: {
      color: '#1D1D1F',
      fontSize: 13,
      fontFamily: 'Inter, -apple-system, sans-serif'
    },
    axisPointer: {
      type: 'cross',
      crossStyle: {
        color: '#86868B'
      },
      lineStyle: {
        color: 'rgba(0, 122, 255, 0.2)',
        width: 1,
        type: 'dashed'
      }
    }
  },
  xAxis: {
    type: 'category',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#86868B',
      fontSize: 11,
      rotate: 45
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: 'rgba(0, 0, 0, 0.04)',
        type: 'dashed'
      }
    }
  },
  yAxis: {
    type: 'value',
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: '#86868B',
      fontSize: 11
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: 'rgba(0, 0, 0, 0.04)',
        type: 'dashed'
      }
    }
  }
})

// Update chart with Apple-style design
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
    const color = getPollutantColor(code)

    series.push({
      name,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      showSymbol: false,
      data: values,
      lineStyle: {
        width: 2.5,
        color: color
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: `${color}30` },
            { offset: 1, color: `${color}05` }
          ]
        }
      },
      emphasis: {
        focus: 'series',
        itemStyle: {
          borderWidth: 2,
          borderColor: '#fff'
        }
      }
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

    const mainColor = '#007AFF'

    legendData.push(historicalName)
    series.push({
      name: historicalName,
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      showSymbol: false,
      data: historicalValues,
      lineStyle: { width: 2.5, color: mainColor },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(0, 122, 255, 0.2)' },
            { offset: 1, color: 'rgba(0, 122, 255, 0.02)' }
          ]
        }
      },
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
        opacity: 0.4,
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(52, 199, 89, 0.3)' },
            { offset: 1, color: 'rgba(52, 199, 89, 0.05)' }
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
      symbol: 'circle',
      symbolSize: 6,
      showSymbol: false,
      data: predictionValues,
      lineStyle: { width: 2.5, type: 'dashed', color: '#34C759' },
      itemStyle: { color: '#34C759' },
      emphasis: { focus: 'series' },
      z: 20
    })

    const yAxisName = `${pollutantLabel} (${valueUnit})`

    const baseOptions = getAppleChartOptions()
    trendChart.setOption({
      ...baseOptions,
      tooltip: {
        ...baseOptions.tooltip,
        formatter: (params: any) => {
          if (!Array.isArray(params)) return ''
          let result = `<div style="font-weight:600;margin-bottom:8px;color:#1D1D1F">${params[0].axisValue}</div>`

          for (const p of params) {
            if (p.value !== null && p.value !== undefined) {
              if (p.seriesName === confidenceLowerName || p.seriesName === confidenceBandName) {
                continue
              }

              const isPrediction = p.seriesName.includes('预测')
              const marker = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:8px;"></span>`
              const formattedValue = formatPollutantValue(selectedPollutant.value, p.value)
              result += `<div style="display:flex;align-items:center;margin:4px 0">${marker}<span style="color:#1D1D1F">${p.seriesName}:</span> <span style="font-weight:600;margin-left:4px">${formattedValue}</span> <span style="color:#86868B;margin-left:2px">${valueUnit}</span>${isPrediction ? '<span style="color:#34C759;font-size:11px;margin-left:6px">(AI)</span>' : ''}</div>`

              if (isPrediction) {
                const timeKey = params[0].axisValue
                const pred = predMap.get(timeKey)
                if (pred) {
                  const lowerFormatted = formatPollutantValue(selectedPollutant.value, pred.lower)
                  const upperFormatted = formatPollutantValue(selectedPollutant.value, pred.upper)
                  result += `<div style="color:#34C759;font-size:11px;margin-left:16px;margin-top:2px">置信区间: [${lowerFormatted}, ${upperFormatted}]</div>`
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
        textStyle: { color: '#86868B', fontSize: 12 },
        selected: { [confidenceLowerName]: false }
      },
      xAxis: {
        ...baseOptions.xAxis,
        data: allTimes
      },
      yAxis: {
        ...baseOptions.yAxis,
        name: yAxisName,
        nameTextStyle: { color: '#86868B', fontSize: 11 },
        scale: true,
        min: (value: { min: number }) => Math.max(0, value.min - Math.abs(value.min) * 0.1),
        max: (value: { max: number }) => value.max + Math.abs(value.max) * 0.1,
        splitNumber: 5,
        axisLabel: {
          ...baseOptions.yAxis.axisLabel,
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

  const baseOptions = getAppleChartOptions()
  trendChart.setOption({
    ...baseOptions,
    tooltip: {
      ...baseOptions.tooltip,
      formatter: (params: any) => {
        if (!Array.isArray(params)) return ''
        let result = `<div style="font-weight:600;margin-bottom:8px;color:#1D1D1F">${params[0].axisValue}</div>`
        for (const p of params) {
          if (p.value !== null && p.value !== undefined) {
            const code = Object.keys(groupedData.value).find(k => getPollutantName(k) === p.seriesName)
            const formattedValue = code ? formatPollutantValue(code, p.value) : p.value.toFixed(2)
            const unit = code ? getPollutantUnit(code) : 'mg/L'
            const marker = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color};margin-right:8px;"></span>`
            result += `<div style="display:flex;align-items:center;margin:4px 0">${marker}<span style="color:#1D1D1F">${p.seriesName}:</span> <span style="font-weight:600;margin-left:4px">${formattedValue}</span> <span style="color:#86868B;margin-left:2px">${unit}</span></div>`
          }
        }
        return result
      }
    },
    legend: {
      data: legendData,
      bottom: 0,
      textStyle: { color: '#86868B', fontSize: 12 }
    },
    xAxis: {
      ...baseOptions.xAxis,
      data: times
    },
    yAxis: {
      ...baseOptions.yAxis,
      name: `${currentPollutantMeta.value.label} (${currentPollutantMeta.value.unit})`,
      nameTextStyle: { color: '#86868B', fontSize: 11 },
      scale: true,
      min: (value: { min: number }) => Math.max(0, value.min - Math.abs(value.min) * 0.1),
      max: (value: { max: number }) => value.max + Math.abs(value.max) * 0.1,
      splitNumber: 5,
      axisLabel: {
        ...baseOptions.yAxis.axisLabel,
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

    <!-- KPI Stats Cards - Apple Style -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-icon" style="background: rgba(0, 122, 255, 0.1)">
          <el-icon size="24" color="#007AFF"><Monitor /></el-icon>
        </div>
        <div class="kpi-content">
          <div class="kpi-value">{{ stats.device_count }}</div>
          <div class="kpi-label">设备总数</div>
          <div class="kpi-detail">
            <span class="online">{{ stats.online_count }} 在线</span>
            <span class="divider">/</span>
            <span class="offline">{{ stats.offline_count }} 离线</span>
          </div>
        </div>
      </div>

      <div class="kpi-card">
        <div class="kpi-icon" style="background: rgba(52, 199, 89, 0.1)">
          <el-icon size="24" color="#34C759"><DataLine /></el-icon>
        </div>
        <div class="kpi-content">
          <div class="kpi-value">{{ trendData.length }}</div>
          <div class="kpi-label">数据点数</div>
          <div class="kpi-detail">24小时内</div>
        </div>
      </div>

      <div class="kpi-card clickable" @click="router.push('/alarms')">
        <div class="kpi-icon" style="background: rgba(255, 149, 0, 0.1)">
          <el-icon size="24" color="#FF9500"><Bell /></el-icon>
        </div>
        <div class="kpi-content">
          <div class="kpi-value">{{ stats.pending_alarms }}</div>
          <div class="kpi-label">异常数据告警</div>
          <div class="kpi-detail">点击查看详情</div>
        </div>
      </div>

      <div class="kpi-card clickable" @click="router.push('/devices')">
        <div class="kpi-icon" style="background: rgba(255, 59, 48, 0.1)">
          <el-icon size="24" color="#FF3B30"><WarningFilled /></el-icon>
        </div>
        <div class="kpi-content">
          <div class="kpi-value">{{ stats.alarm_count }}</div>
          <div class="kpi-label">异常设备</div>
          <div class="kpi-detail">点击查看详情</div>
        </div>
      </div>
    </div>

    <!-- Real-time Monitoring Cards -->
    <el-card class="monitoring-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">实时监测数据</span>
          <div class="header-right">
            <div class="preset-buttons">
              <template v-for="preset in pollutantPresets" :key="preset.value">
                <el-dropdown
                  v-if="preset.hasSubmenu"
                  trigger="click"
                  @command="(cmd: string) => { onPresetChange(preset.value); onHeavyMetalFilterChange(cmd === 'all' ? null : cmd === 'class1' ? 'heavy_metals_class1' : 'heavy_metals_class2'); }"
                >
                  <el-button
                    :type="selectedPreset === preset.value ? 'primary' : 'default'"
                    size="small"
                    round
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
                <el-button
                  v-else
                  :type="selectedPreset === preset.value ? 'primary' : 'default'"
                  size="small"
                  round
                  @click="onPresetChange(preset.value)"
                >
                  {{ preset.label }}
                </el-button>
              </template>
            </div>
          </div>
        </div>
        <!-- Heavy metal sub-filter tags -->
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

      <!-- Pollutant cards -->
      <div v-if="monitoringCards.length > 0" class="pollutant-grid">
        <div
          v-for="card in monitoringCards"
          :key="card.code"
          class="pollutant-card"
          :class="{ 'heavy-metal': card.isHeavyMetal }"
        >
          <div class="pollutant-icon" :style="{ background: `${card.color}15` }">
            <div class="icon-dot" :style="{ background: card.color }"></div>
          </div>
          <div class="pollutant-info">
            <div class="pollutant-header">
              <span class="pollutant-name">{{ card.name }}</span>
              <el-tag
                :type="card.flag === 'N' ? 'success' : 'warning'"
                size="small"
                round
              >
                {{ card.flag }}
              </el-tag>
            </div>
            <div class="pollutant-value">
              <template v-if="card.value !== undefined">
                <span class="value" :style="{ color: card.color }">{{ card.value.toFixed(card.precision) }}</span>
                <span class="unit">{{ card.unit }}</span>
              </template>
              <template v-else>
                <span class="value no-data">--</span>
              </template>
            </div>
            <div class="pollutant-code">{{ card.code }}</div>
          </div>
        </div>
      </div>

      <!-- Expand button -->
      <div v-if="showExpandButton" class="expand-container">
        <el-button type="primary" link @click="toggleExpand">
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

      <!-- No data hint -->
      <div v-else-if="monitoringCards.length === 0" class="no-data-hint">
        <el-empty description="暂无监测数据">
          <template #description>
            <p>当前设备尚未上报数据</p>
            <p class="hint-text">数据将在设备数采仪上报后自动显示</p>
          </template>
        </el-empty>
      </div>
    </el-card>

    <!-- Device Map -->
    <el-card class="map-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">设备分布地图</span>
          <el-tag type="info" size="small" round>{{ devices.length }} 台设备</el-tag>
        </div>
      </template>
      <DeviceMap
        :devices="devices"
        :loading="loading"
        height="400px"
        @device-click="handleDeviceClick"
      />
    </el-card>

    <!-- Charts -->
    <el-card class="chart-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span class="card-title">{{ currentPollutantMeta.label }} 实时趋势 + AI预测</span>
            <el-tag v-if="predictionData?.model_type" type="success" size="small" round>
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
        <el-tag type="info" size="small" round>
          预测时间范围: 未来 {{ predictionData.predictions.length * 15 }} 分钟
        </el-tag>
        <el-tag v-if="predictionData.metrics?.interval_width" type="success" size="small" round>
          置信区间: {{ (predictionData.metrics.interval_width * 100).toFixed(0) }}%
        </el-tag>
        <el-tag v-if="predictionData.metrics?.data_points" type="warning" size="small" round>
          训练数据: {{ predictionData.metrics.data_points }} 点
        </el-tag>
      </div>
      <div v-if="trendData.length === 0 && !loading" class="no-data">
        暂无监测数据
      </div>
    </el-card>

    <!-- AI Analysis Card -->
    <AiAnalysisCard
      :device-id="selectedDeviceForPrediction"
      :device-name="selectedDeviceName"
    />

    <!-- Data table -->
    <el-card class="data-card">
      <template #header>
        <span class="card-title">最新监测数据</span>
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
            <el-tag :type="row.flag === 'N' ? 'success' : 'warning'" size="small" round>
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
  </div>
</template>

<script lang="ts">
import { Refresh, ArrowDown, ArrowUp } from '@element-plus/icons-vue'
export default {
  components: { Refresh, ArrowDown, ArrowUp }
}
</script>

<style scoped>
.dashboard {
  padding: var(--space-lg);
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.error-alert {
  border-radius: var(--radius-lg);
}

/* KPI Cards Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-lg);
}

@media (max-width: 1200px) {
  .kpi-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .kpi-grid {
    grid-template-columns: 1fr;
  }
}

.kpi-card {
  background: var(--color-bg-secondary);
  border-radius: var(--radius-xl);
  padding: var(--space-lg);
  box-shadow: var(--shadow-md);
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  transition: transform var(--transition-normal), box-shadow var(--transition-normal);
}

.kpi-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-lg);
}

.kpi-card.clickable {
  cursor: pointer;
}

.kpi-card.clickable:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-xl);
}

.kpi-card.clickable:active {
  transform: translateY(0);
  box-shadow: var(--shadow-md);
}

.kpi-icon {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.kpi-content {
  flex: 1;
  min-width: 0;
}

.kpi-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-text-primary);
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.kpi-label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin-top: 4px;
}

.kpi-detail {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 8px;
}

.kpi-detail .online {
  color: #34C759;
}

.kpi-detail .offline {
  color: var(--color-text-tertiary);
}

.kpi-detail .divider {
  margin: 0 6px;
  color: var(--color-text-tertiary);
}

/* Card Headers */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-md);
}

.card-title {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.preset-buttons {
  display: flex;
  gap: var(--space-sm);
}

/* Sub filter tags */
.sub-filter-tags {
  margin-top: var(--space-md);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.sub-tag {
  cursor: pointer;
  transition: transform var(--transition-fast);
}

.sub-tag:hover {
  transform: scale(1.05);
}

.filter-hint {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  margin-left: var(--space-sm);
}

.active-filter {
  color: var(--color-accent-blue);
  font-weight: 600;
}

/* Pollutant Cards Grid */
.pollutant-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-md);
}

@media (max-width: 1400px) {
  .pollutant-grid {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 1000px) {
  .pollutant-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 600px) {
  .pollutant-grid {
    grid-template-columns: 1fr;
  }
}

.pollutant-card {
  background: var(--color-bg-tertiary);
  border-radius: var(--radius-lg);
  padding: var(--space-md);
  display: flex;
  align-items: flex-start;
  gap: var(--space-md);
  transition: all var(--transition-normal);
}

.pollutant-card:hover {
  background: #EAEAEF;
  transform: translateY(-2px);
}

.pollutant-card.heavy-metal {
  background: linear-gradient(135deg, rgba(175, 82, 222, 0.08) 0%, var(--color-bg-tertiary) 100%);
}

.pollutant-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.pollutant-info {
  flex: 1;
  min-width: 0;
}

.pollutant-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.pollutant-name {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.pollutant-value {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.pollutant-value .value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  letter-spacing: -0.02em;
}

.pollutant-value .value.no-data {
  color: var(--color-text-tertiary);
}

.pollutant-value .unit {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
}

.pollutant-code {
  font-size: var(--font-size-xs);
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

/* Expand container */
.expand-container {
  text-align: center;
  padding-top: var(--space-md);
  border-top: 1px dashed rgba(0, 0, 0, 0.06);
  margin-top: var(--space-md);
}

/* No data hint */
.no-data-hint {
  padding: var(--space-xl) 0;
  text-align: center;
}

.no-data-hint .hint-text {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  margin-top: var(--space-sm);
}

/* Chart card */
.chart-card {
  min-height: 500px;
}

.prediction-info {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-md) 0;
  justify-content: center;
}

.no-data {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-base);
}

/* Data table */
.data-card .code-hint {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  margin-left: 4px;
}

.data-card .heavy-metal-value {
  color: #AF52DE;
}

.data-card .value-unit {
  margin-left: 4px;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
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

:deep(.el-button--warning) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
  color: #fff !important;
}

:deep(.el-button--warning:hover),
:deep(.el-button--warning:focus) {
  background-color: #162a3d !important;
  border-color: #162a3d !important;
}

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

/* 圆形刷新按钮 */
:deep(.el-button.is-circle.el-button--primary) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
}

:deep(.el-button.is-circle.el-button--primary:hover) {
  background-color: #162a3d !important;
  border-color: #162a3d !important;
}

/* link 类型按钮 */
:deep(.el-button--primary.is-link) {
  color: #0B1727 !important;
  background: transparent !important;
}

:deep(.el-button--primary.is-link:hover) {
  color: #162a3d !important;
}
</style>
