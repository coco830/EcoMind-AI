<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import {
  regulatorApi,
  type RegulatorOverview,
  type RegulatorHeatmap,
  type RegulatorTrends,
  type RegulatorConsistency
} from '@/api/regulator'
import RegulatorHeatmapMap from '@/components/RegulatorHeatmapMap.vue'

const loading = ref(false)
const overview = ref<RegulatorOverview | null>(null)
const heatmap = ref<RegulatorHeatmap | null>(null)
const trends = ref<RegulatorTrends | null>(null)
const consistency = ref<RegulatorConsistency | null>(null)

const targetDate = ref<string>(getYesterday())
const resolution = ref(7)
const regionCode = ref('')
const parkCode = ref('')
const trendGranularity = ref<'daily' | 'monthly'>('daily')

const riskChartRef = ref<HTMLDivElement | null>(null)
const trendChartRef = ref<HTMLDivElement | null>(null)
let riskChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

const riskColors: Record<string, string> = {
  L1: '#3ABF7B',
  L2: '#8BCF5B',
  L3: '#F4C45C',
  L4: '#F29D4B',
  L5: '#E85B5B'
}

function getYesterday(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

function offsetDate(dateStr: string, offsetDays: number): string {
  const d = new Date(`${dateStr}T00:00:00`)
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

const fetchAll = async () => {
  loading.value = true
  const endDate = targetDate.value || getYesterday()
  const startDate = offsetDate(endDate, -29)

  try {
    const [overviewRes, heatmapRes, trendsRes, consistencyRes] = await Promise.all([
      regulatorApi.getOverview({
        target_date: endDate,
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      }),
      regulatorApi.getHeatmap({
        target_date: endDate,
        resolution: resolution.value,
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      }),
      regulatorApi.getTrends({
        start_date: startDate,
        end_date: endDate,
        granularity: trendGranularity.value
      }),
      regulatorApi.getConsistency({
        start_date: startDate,
        end_date: endDate
      })
    ])

    overview.value = overviewRes
    heatmap.value = heatmapRes
    trends.value = trendsRes
    consistency.value = consistencyRes
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '加载监管数据失败')
  } finally {
    loading.value = false
    renderRiskChart()
    renderTrendChart()
  }
}

const initCharts = () => {
  if (riskChartRef.value) {
    riskChart = echarts.init(riskChartRef.value)
  }
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
  }
  window.addEventListener('resize', handleResize)
}

const handleResize = () => {
  riskChart?.resize()
  trendChart?.resize()
}

const renderRiskChart = () => {
  if (!riskChart || !overview.value) return
  const distribution = overview.value.risk_distribution || []
  const levels = ['L1', 'L2', 'L3', 'L4', 'L5']
  const counts = levels.map(level => {
    const item = distribution.find(d => d.level === level)
    return item ? item.count : 0
  })

  riskChart.setOption({
    grid: { left: 24, right: 16, top: 30, bottom: 24 },
    xAxis: { type: 'category', data: levels },
    yAxis: { type: 'value' },
    tooltip: { trigger: 'axis' },
    series: [
      {
        type: 'bar',
        data: counts,
        itemStyle: {
          color: (params: any) => riskColors[levels[params.dataIndex]] || '#5B8FF9'
        },
        barWidth: 22
      }
    ]
  })
}

const renderTrendChart = () => {
  if (!trendChart || !trends.value) return
  const seriesData = trends.value.series || []
  const dates = seriesData.map(item => item.date)
  const levels = ['L1', 'L2', 'L3', 'L4', 'L5']
  const levelMap: Record<string, number[]> = {
    L1: [],
    L2: [],
    L3: [],
    L4: [],
    L5: []
  }

  seriesData.forEach(item => {
    levels.forEach(level => {
      const match = item.risk_distribution.find(entry => entry.level === level)
      levelMap[level].push(match ? match.count : 0)
    })
  })

  trendChart.setOption({
    grid: { left: 32, right: 24, top: 40, bottom: 24 },
    tooltip: { trigger: 'axis' },
    legend: { data: levels, right: 8, top: 8 },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: levels.map(level => ({
      name: level,
      type: 'line',
      smooth: true,
      data: levelMap[level],
      color: riskColors[level] || '#5B8FF9'
    }))
  })
}

watch(trendGranularity, () => {
  fetchAll()
})

onMounted(async () => {
  initCharts()
  await fetchAll()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  riskChart?.dispose()
  trendChart?.dispose()
  riskChart = null
  trendChart = null
})
</script>

<template>
  <div class="regulator-dashboard">
    <div class="filter-bar">
      <el-date-picker
        v-model="targetDate"
        type="date"
        placeholder="选择日期"
        value-format="YYYY-MM-DD"
        format="YYYY-MM-DD"
      />
      <el-select v-model="resolution" placeholder="H3 分辨率" style="width: 140px">
        <el-option v-for="item in [6,7,8,9]" :key="item" :label="`H3-${item}`" :value="item" />
      </el-select>
      <el-input v-model="regionCode" placeholder="区县编码 (可选)" style="width: 160px" />
      <el-input v-model="parkCode" placeholder="园区编码 (可选)" style="width: 160px" />
      <el-select v-model="trendGranularity" placeholder="趋势周期" style="width: 140px">
        <el-option label="按日" value="daily" />
        <el-option label="按月" value="monthly" />
      </el-select>
      <el-button type="primary" :loading="loading" @click="fetchAll">刷新</el-button>
    </div>
    <div class="filter-note">
      数据延迟 T+1；风险分=0.4×超标率 + 0.2×无效率 + 0.2×离线率 + 0.2×报警率。
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">企业数量</div>
          <div class="stat-value">{{ overview?.enterprise_count ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">设备总数</div>
          <div class="stat-value">{{ overview?.device_count ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">在线设备</div>
          <div class="stat-value">{{ overview?.online_device_count ?? 0 }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">离线设备</div>
          <div class="stat-value">{{ overview?.offline_device_count ?? 0 }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" class="main-row">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">风险热力 (H3 网格)</div>
          </template>
          <RegulatorHeatmapMap :cells="heatmap?.cells || []" height="360px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <div class="card-header">风险等级分布</div>
          </template>
          <div ref="riskChartRef" class="chart-box"></div>
          <div class="risk-note">
            L1 低(0-20) · L2 偏低(20-40) · L3 中(40-60) · L4 较高(60-80) · L5 高(80-100)
          </div>
        </el-card>
        <el-card class="consistency-card">
          <template #header>
            <div class="card-header">一致性评估</div>
          </template>
          <div class="consistency-grid">
            <div class="consistency-item">
              <div class="consistency-label">高一致</div>
              <div class="consistency-value">{{ consistency?.summary.high ?? 0 }}</div>
            </div>
            <div class="consistency-item">
              <div class="consistency-label">中一致</div>
              <div class="consistency-value">{{ consistency?.summary.medium ?? 0 }}</div>
            </div>
            <div class="consistency-item">
              <div class="consistency-label">低一致</div>
              <div class="consistency-value">{{ consistency?.summary.low ?? 0 }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="trend-card">
      <template #header>
        <div class="card-header">风险趋势</div>
      </template>
      <div ref="trendChartRef" class="trend-chart"></div>
    </el-card>

    <el-row :gutter="16" class="distribution-row">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">行业分布</div>
          </template>
          <el-table
            :data="overview?.industry_distribution || []"
            size="small"
            style="width: 100%"
            :header-cell-style="{ background: '#FAFAFA', color: '#1D1D1F', fontWeight: '600' }"
          >
            <el-table-column prop="industry" label="行业" min-width="120" />
            <el-table-column prop="count" label="企业数" width="100" />
            <el-table-column label="样本不足" width="100">
              <template #default="{ row }">
                <el-tag v-if="row.insufficient" type="warning" size="small">是</el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">区域分布</div>
          </template>
          <el-table
            :data="overview?.region_distribution || []"
            size="small"
            style="width: 100%"
            :header-cell-style="{ background: '#FAFAFA', color: '#1D1D1F', fontWeight: '600' }"
          >
            <el-table-column prop="region_code" label="区域编码" min-width="140" />
            <el-table-column prop="count" label="企业数" width="100" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.regulator-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.filter-note {
  font-size: 12px;
  color: #6b7280;
}

.summary-row .el-card {
  border-radius: 12px;
}

.stat-card {
  text-align: center;
}

.stat-label {
  font-size: 13px;
  color: #6b7280;
}

.stat-value {
  font-size: 24px;
  font-weight: 600;
  color: #1d1d1f;
  margin-top: 8px;
}

.card-header {
  font-weight: 600;
  color: #1d1d1f;
}

.chart-card {
  margin-bottom: 16px;
}

.chart-box {
  height: 220px;
}

.risk-note {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.4;
}

.consistency-card {
  border-radius: 12px;
}

.consistency-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.consistency-item {
  text-align: center;
  padding: 8px;
  border-radius: 10px;
  background: #f6f7fb;
}

.consistency-label {
  font-size: 12px;
  color: #6b7280;
}

.consistency-value {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  margin-top: 4px;
}

.trend-card {
  border-radius: 12px;
}

.trend-chart {
  height: 280px;
}
</style>
