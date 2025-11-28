<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { reportApi, type ReportPreview, type ReportDevice, type ReportRequest } from '@/api/reports'
import { ElMessage } from 'element-plus'
import { Document, Download, View, Calendar } from '@element-plus/icons-vue'

// State
const loading = ref(false)
const downloadLoading = ref(false)
const devices = ref<ReportDevice[]>([])
const selectedDevice = ref('')
const reportType = ref<'daily' | 'monthly'>('daily')
const reportDate = ref<Date>(new Date())
const reportYear = ref(new Date().getFullYear())
const reportMonth = ref(new Date().getMonth() + 1)
const preview = ref<ReportPreview | null>(null)

// Computed
const selectedDeviceInfo = computed(() => {
  return devices.value.find(d => d.id === selectedDevice.value)
})

const canGenerate = computed(() => {
  return !!selectedDevice.value
})

// Methods
const loadDevices = async () => {
  try {
    devices.value = await reportApi.listDevices()
    if (devices.value.length > 0) {
      selectedDevice.value = devices.value[0].id
    }
  } catch (error) {
    ElMessage.error('加载设备列表失败')
  }
}

const buildReportRequest = (): ReportRequest => {
  const req: ReportRequest = {
    device_id: selectedDevice.value,
    report_type: reportType.value
  }

  if (reportType.value === 'daily') {
    const d = reportDate.value
    req.report_date = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  } else {
    req.year = reportYear.value
    req.month = reportMonth.value
  }

  return req
}

const generatePreview = async () => {
  if (!canGenerate.value) {
    ElMessage.warning('请先选择设备')
    return
  }

  loading.value = true
  preview.value = null

  try {
    const req = buildReportRequest()
    preview.value = await reportApi.preview(req)
    ElMessage.success('预览生成成功')
  } catch (error) {
    ElMessage.error('生成预览失败')
  } finally {
    loading.value = false
  }
}

const downloadReport = async (format: 'excel' | 'pdf') => {
  if (!canGenerate.value) {
    ElMessage.warning('请先选择设备')
    return
  }

  downloadLoading.value = true

  try {
    const req = buildReportRequest()
    await reportApi.download(req, format)
    ElMessage.success(`${format.toUpperCase()} 下载成功`)
  } catch (error) {
    ElMessage.error(`${format.toUpperCase()} 下载失败`)
  } finally {
    downloadLoading.value = false
  }
}

const formatNumber = (val: number | null, decimals = 2) => {
  if (val === null || val === undefined) return '-'
  return val.toFixed(decimals)
}

const getDeviceTypeName = (type: string) => {
  const types: Record<string, string> = {
    water: '水质',
    air: '大气',
    noise: '噪声',
    soil: '土壤'
  }
  return types[type] || type
}

// Clear preview when parameters change
watch([selectedDevice, reportType, reportDate, reportYear, reportMonth], () => {
  preview.value = null
})

// Initialize
onMounted(() => {
  loadDevices()
})
</script>

<template>
  <div class="reports-page">
    <!-- 查询面板 -->
    <el-card class="query-card">
      <template #header>
        <div class="card-header">
          <el-icon><Document /></el-icon>
          <span>报表中心</span>
        </div>
      </template>

      <el-form label-width="100px" label-position="left">
        <el-row :gutter="24">
          <!-- 设备选择 -->
          <el-col :span="8">
            <el-form-item label="监测设备">
              <el-select
                v-model="selectedDevice"
                placeholder="请选择设备"
                style="width: 100%"
                filterable
              >
                <el-option
                  v-for="device in devices"
                  :key="device.id"
                  :label="`${device.name} (${device.mn})`"
                  :value="device.id"
                >
                  <span style="float: left">{{ device.name }}</span>
                  <span style="float: right; color: #8492a6; font-size: 13px">
                    {{ getDeviceTypeName(device.device_type) }}
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>

          <!-- 报表类型 -->
          <el-col :span="6">
            <el-form-item label="报表类型">
              <el-radio-group v-model="reportType">
                <el-radio-button value="daily">日报</el-radio-button>
                <el-radio-button value="monthly">月报</el-radio-button>
              </el-radio-group>
            </el-form-item>
          </el-col>

          <!-- 日期选择 -->
          <el-col :span="6">
            <el-form-item label="统计周期">
              <el-date-picker
                v-if="reportType === 'daily'"
                v-model="reportDate"
                type="date"
                placeholder="选择日期"
                style="width: 100%"
                :disabled-date="(date: Date) => date > new Date()"
              />
              <div v-else class="month-picker">
                <el-select v-model="reportYear" style="width: 100px">
                  <el-option
                    v-for="year in [2024, 2025]"
                    :key="year"
                    :label="`${year}年`"
                    :value="year"
                  />
                </el-select>
                <el-select v-model="reportMonth" style="width: 100px">
                  <el-option
                    v-for="month in 12"
                    :key="month"
                    :label="`${month}月`"
                    :value="month"
                  />
                </el-select>
              </div>
            </el-form-item>
          </el-col>

          <!-- 操作按钮 -->
          <el-col :span="4">
            <el-form-item label=" ">
              <el-button
                type="primary"
                :loading="loading"
                :disabled="!canGenerate"
                @click="generatePreview"
              >
                <el-icon><View /></el-icon>
                预览
              </el-button>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <!-- 设备信息 -->
      <div v-if="selectedDeviceInfo" class="device-info">
        <el-tag type="info" size="small">设备编号: {{ selectedDeviceInfo.mn }}</el-tag>
        <el-tag type="success" size="small">{{ getDeviceTypeName(selectedDeviceInfo.device_type) }}</el-tag>
        <el-tag
          v-for="code in (selectedDeviceInfo.pollutant_codes || []).slice(0, 5)"
          :key="code"
          size="small"
        >
          {{ code }}
        </el-tag>
        <el-tag v-if="(selectedDeviceInfo.pollutant_codes || []).length > 5" size="small">
          +{{ (selectedDeviceInfo.pollutant_codes || []).length - 5 }} 更多
        </el-tag>
      </div>
    </el-card>

    <!-- 预览结果 -->
    <el-card v-if="preview" class="preview-card">
      <template #header>
        <div class="card-header">
          <div>
            <el-icon><Calendar /></el-icon>
            <span>报表预览: {{ preview.device_name }}</span>
          </div>
          <div class="download-buttons">
            <el-button
              type="success"
              :loading="downloadLoading"
              @click="downloadReport('excel')"
            >
              <el-icon><Download /></el-icon>
              下载 Excel
            </el-button>
            <el-button
              type="primary"
              :loading="downloadLoading"
              @click="downloadReport('pdf')"
            >
              <el-icon><Download /></el-icon>
              下载 PDF
            </el-button>
          </div>
        </div>
      </template>

      <!-- 统计摘要 -->
      <el-row :gutter="20" class="summary-row">
        <el-col :span="6">
          <el-statistic title="统计天数" :value="preview.period.days">
            <template #suffix>
              <span class="stat-unit">天</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="数据记录数" :value="preview.summary.total_records" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="数据捕获率" :value="preview.summary.capture_rate">
            <template #suffix>
              <span class="stat-unit">%</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="超标次数"
            :value="preview.summary.exceedance_count"
            :value-style="{ color: preview.summary.exceedance_count > 0 ? '#f56c6c' : '#67c23a' }"
          />
        </el-col>
      </el-row>

      <!-- 污染物统计表 -->
      <el-table
        :data="preview.pollutants"
        stripe
        border
        class="stats-table"
      >
        <el-table-column prop="pollutant_code" label="参数编码" width="100" />
        <el-table-column prop="pollutant_name" label="污染物名称" width="150" />
        <el-table-column prop="unit" label="单位" width="80" align="center" />
        <el-table-column label="最小值" width="100" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.min_value) }}
          </template>
        </el-table-column>
        <el-table-column label="最大值" width="100" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.max_value) }}
          </template>
        </el-table-column>
        <el-table-column label="平均值" width="100" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.avg_value) }}
          </template>
        </el-table-column>
        <el-table-column label="标准差" width="100" align="right">
          <template #default="{ row }">
            {{ formatNumber(row.std_value) }}
          </template>
        </el-table-column>
        <el-table-column prop="data_count" label="记录数" width="90" align="center" />
        <el-table-column label="阈值" width="100" align="right">
          <template #default="{ row }">
            {{ row.threshold ? formatNumber(row.threshold) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="超标次数" width="110" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.exceedance_count > 0 ? 'danger' : 'success'"
              size="small"
            >
              {{ row.exceedance_count }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>

      <!-- 统计周期 -->
      <div class="period-info">
        <span>统计周期: {{ preview.period.start }} ~ {{ preview.period.end }}</span>
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-card v-else-if="!loading" class="empty-card">
      <el-empty description="请选择设备并点击预览按钮生成报表统计">
        <el-button type="primary" :disabled="!canGenerate" @click="generatePreview">
          生成预览
        </el-button>
      </el-empty>
    </el-card>

    <!-- 加载状态 -->
    <el-card v-if="loading" class="loading-card">
      <div v-loading="true" class="loading-content">
        正在生成报表预览...
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.reports-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card-header > div:first-child {
  display: flex;
  align-items: center;
  gap: 8px;
}

.device-info {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.month-picker {
  display: flex;
  gap: 8px;
}

.download-buttons {
  display: flex;
  gap: 12px;
}

.summary-row {
  margin-bottom: 24px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.stat-unit {
  font-size: 14px;
  color: #909399;
}

.stats-table {
  margin-bottom: 16px;
}

.period-info {
  text-align: right;
  color: #909399;
  font-size: 13px;
}

.empty-card,
.loading-card {
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-content {
  height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
