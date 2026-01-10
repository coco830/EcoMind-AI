<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Upload,
  Document,
  Search,
  Check,
  Close,
  TrendCharts,
  MagicStick,
  View,
  Delete,
  Calendar,
  UploadFilled,
  Refresh
} from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'
import * as echarts from 'echarts'
import {
  selfInspectionApi,
  type SelfInspectionReport,
  type SelfInspectionReportListItem,
  type SelfInspectionDataItem,
  type OCRUploadResponse,
  type TrendAnalysisResponse,
  type AIReportResponse,
  type InspectionStatus
} from '@/api/selfInspection'

// ============== State ==============
const loading = ref(false)
const uploadLoading = ref(false)
const verifyLoading = ref(false)
const trendLoading = ref(false)
const aiReportLoading = ref(false)

// List state
const reports = ref<SelfInspectionReportListItem[]>([])
const totalReports = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const filterStatus = ref<InspectionStatus | ''>('')
const filterDateRange = ref<[Date, Date] | null>(null)

// Upload dialog
const uploadDialogVisible = ref(false)
const uploadForm = reactive({
  file: null as File | null,
  inspection_date: '',
  inspection_agency: '',
  report_number: '',
  use_ai_parsing: true  // AI智能解析开关
})
const uploadFileList = ref<UploadFile[]>()
const ocrProgressVisible = ref(false)
const ocrProgressSteps = ref<{ step: string; status: 'process' | 'success' | 'error' }[]>([])

// Verify dialog
const verifyDialogVisible = ref(false)
const currentReport = ref<SelfInspectionReport | null>(null)
const editableDataItems = ref<SelfInspectionDataItem[]>([])
const ocrRawText = ref('')

// Trend Analysis
const trendDialogVisible = ref(false)
const trendDateRange = ref<[Date, Date] | null>(null)
const trendData = ref<TrendAnalysisResponse | null>(null)
const trendChartRef = ref<HTMLDivElement | null>(null)
let trendChart: echarts.ECharts | null = null

// AI Report
const aiReportDialogVisible = ref(false)
const aiReportDateRange = ref<[Date, Date] | null>(null)
const aiReportType = ref<'monthly' | 'quarterly'>('monthly')
const aiReport = ref<AIReportResponse | null>(null)

// ============== Computed ==============
const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待校验' },
  { value: 'verified', label: '已校验' },
  { value: 'rejected', label: '已拒绝' }
]

// AI智能解析模式下，只需要文件；传统模式需要填写日期和机构
const canUpload = computed(() => {
  if (uploadForm.use_ai_parsing) {
    return !!uploadForm.file
  }
  return uploadForm.file && uploadForm.inspection_date && uploadForm.inspection_agency
})

// ============== Methods ==============

// Format date to YYYY-MM-DD
const formatDate = (date: Date | string): string => {
  if (!date) return ''
  const d = new Date(date)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Load reports list
const loadReports = async () => {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    if (filterDateRange.value) {
      params.start_date = formatDate(filterDateRange.value[0])
      params.end_date = formatDate(filterDateRange.value[1])
    }

    const result = await selfInspectionApi.list(params)
    reports.value = result.items
    totalReports.value = result.total
  } catch (error) {
    ElMessage.error('加载报告列表失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

// Handle file change
const handleFileChange = (file: UploadFile) => {
  if (file.raw) {
    const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/jpg']
    if (!allowedTypes.includes(file.raw.type)) {
      ElMessage.warning('仅支持 PDF、JPG、PNG 格式文件')
      uploadFileList.value = []
      return
    }
    if (file.raw.size > 20 * 1024 * 1024) {
      ElMessage.warning('文件大小不能超过 20MB')
      uploadFileList.value = []
      return
    }
    uploadForm.file = file.raw
  }
}

const handleFileRemove = () => {
  uploadForm.file = null
  uploadFileList.value = []
}

// Show upload dialog
const showUploadDialog = () => {
  uploadForm.file = null
  uploadForm.inspection_date = ''
  uploadForm.inspection_agency = ''
  uploadForm.report_number = ''
  uploadForm.use_ai_parsing = true
  uploadFileList.value = []
  ocrProgressVisible.value = false
  ocrProgressSteps.value = []
  uploadDialogVisible.value = true
}

// Upload and OCR with AI parsing
const handleUpload = async () => {
  if (!canUpload.value || !uploadForm.file) {
    ElMessage.warning(uploadForm.use_ai_parsing ? '请选择文件' : '请填写完整信息并选择文件')
    return
  }

  uploadLoading.value = true
  ocrProgressVisible.value = true
  ocrProgressSteps.value = [
    { step: '上传文件', status: 'process' }
  ]

  try {
    // 显示处理进度
    if (uploadForm.use_ai_parsing) {
      ocrProgressSteps.value = [
        { step: '上传文件', status: 'process' },
        { step: 'OCR表格识别', status: 'process' },
        { step: 'AI智能解析', status: 'process' }
      ]
    } else {
      ocrProgressSteps.value = [
        { step: '上传文件', status: 'process' },
        { step: 'OCR识别', status: 'process' }
      ]
    }

    // 模拟进度更新
    ocrProgressSteps.value[0].status = 'success'

    const result: OCRUploadResponse = await selfInspectionApi.upload(
      uploadForm.file,
      uploadForm.inspection_date || undefined,
      uploadForm.inspection_agency || undefined,
      uploadForm.report_number || undefined,
      uploadForm.use_ai_parsing
    )

    // 更新进度为完成
    ocrProgressSteps.value.forEach(step => step.status = 'success')

    ElMessage.success(result.message || '解析完成')

    // 短暂显示成功状态后关闭对话框
    setTimeout(async () => {
      uploadDialogVisible.value = false

      // Auto open verify dialog
      const report = await selfInspectionApi.get(result.report_id)
      openVerifyDialog(report)

      // Refresh list
      loadReports()
    }, 800)

  } catch (error: unknown) {
    const errMsg = error instanceof Error ? error.message : '上传失败'
    ElMessage.error(errMsg)
    console.error(error)

    // 更新进度为失败
    const processingStep = ocrProgressSteps.value.find(s => s.status === 'process')
    if (processingStep) {
      processingStep.status = 'error'
    }
  } finally {
    uploadLoading.value = false
  }
}

// Open verify dialog
const openVerifyDialog = async (report: SelfInspectionReport | SelfInspectionReportListItem) => {
  verifyLoading.value = true
  try {
    // If it's a list item, fetch full details
    let fullReport: SelfInspectionReport
    if ('data_items' in report) {
      fullReport = report
    } else {
      fullReport = await selfInspectionApi.get(report.id)
    }

    currentReport.value = fullReport
    editableDataItems.value = JSON.parse(JSON.stringify(fullReport.data_items || []))
    ocrRawText.value = '' // Backend doesn't return raw text in response
    verifyDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载报告详情失败')
    console.error(error)
  } finally {
    verifyLoading.value = false
  }
}

// Add new data item
const addDataItem = () => {
  editableDataItems.value.push({
    pollutant_code: '',
    pollutant_name: '',
    value: 0,
    unit: 'mg/L',
    standard_limit: null,
    is_compliant: true,
    sampling_point: null,
    sampling_time: null
  })
}

// Remove data item
const removeDataItem = (index: number) => {
  editableDataItems.value.splice(index, 1)
}

// Verify report
const verifyReport = async (status: 'verified' | 'rejected') => {
  if (!currentReport.value) return

  verifyLoading.value = true
  try {
    await selfInspectionApi.update(currentReport.value.id, {
      status,
      data_items: editableDataItems.value.map(item => ({
        pollutant_code: item.pollutant_code,
        pollutant_name: item.pollutant_name,
        value: item.value,
        unit: item.unit,
        standard_limit: item.standard_limit,
        is_compliant: item.is_compliant,
        sampling_point: item.sampling_point,
        sampling_time: item.sampling_time
      }))
    })

    ElMessage.success(status === 'verified' ? '校验通过' : '已拒绝')
    verifyDialogVisible.value = false
    loadReports()
  } catch (error) {
    ElMessage.error('操作失败')
    console.error(error)
  } finally {
    verifyLoading.value = false
  }
}

// Delete report
const deleteReport = async (report: SelfInspectionReportListItem) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除检测日期为 ${report.inspection_date} 的报告吗？此操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '确定删除', cancelButtonText: '取消', type: 'warning' }
    )

    await selfInspectionApi.delete(report.id)
    ElMessage.success('删除成功')
    loadReports()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error(error)
    }
  }
}

// Show trend analysis dialog
const showTrendDialog = () => {
  // Default to last 3 months
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 3)
  trendDateRange.value = [start, end]
  trendData.value = null
  trendDialogVisible.value = true
}

// Fetch trend analysis
const fetchTrendAnalysis = async () => {
  if (!trendDateRange.value) {
    ElMessage.warning('请选择日期范围')
    return
  }

  trendLoading.value = true
  try {
    const result = await selfInspectionApi.getTrendAnalysis({
      start_date: formatDate(trendDateRange.value[0]),
      end_date: formatDate(trendDateRange.value[1])
    })

    trendData.value = result

    // Render chart after data loaded
    setTimeout(() => renderTrendChart(), 100)
  } catch (error) {
    ElMessage.error('获取趋势数据失败')
    console.error(error)
  } finally {
    trendLoading.value = false
  }
}

// Render trend chart
const renderTrendChart = () => {
  if (!trendChartRef.value || !trendData.value) return

  if (trendChart) {
    trendChart.dispose()
  }

  trendChart = echarts.init(trendChartRef.value)

  // Group data by pollutant
  const pollutantMap = new Map<string, { dates: string[]; values: number[]; name: string }>()

  trendData.value.data_points.forEach(point => {
    if (!pollutantMap.has(point.pollutant_code)) {
      pollutantMap.set(point.pollutant_code, {
        dates: [],
        values: [],
        name: point.pollutant_name
      })
    }
    const data = pollutantMap.get(point.pollutant_code)!
    data.dates.push(point.date)
    data.values.push(point.value)
  })

  const series: echarts.SeriesOption[] = []
  const legendData: string[] = []

  pollutantMap.forEach((data) => {
    legendData.push(data.name)
    series.push({
      name: data.name,
      type: 'line',
      smooth: true,
      data: data.values,
      symbol: 'circle',
      symbolSize: 6
    })
  })

  // Get all unique dates for xAxis
  const allDates = [...new Set(trendData.value.data_points.map(p => p.date))].sort()

  const option: echarts.EChartsOption = {
    title: {
      text: '污染物浓度趋势',
      left: 'center',
      textStyle: { fontSize: 16, fontWeight: 500, color: '#1D1D1F' }
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255,255,255,0.95)',
      borderColor: '#e0e0e0',
      textStyle: { color: '#333' }
    },
    legend: {
      data: legendData,
      bottom: 0,
      textStyle: { color: '#666' }
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
      data: allDates,
      axisLine: { lineStyle: { color: '#e0e0e0' } },
      axisLabel: { color: '#666' }
    },
    yAxis: {
      type: 'value',
      name: '浓度',
      axisLine: { lineStyle: { color: '#e0e0e0' } },
      axisLabel: { color: '#666' },
      splitLine: { lineStyle: { color: '#f0f0f0' } }
    },
    series,
    color: ['#0B1727', '#1D6F42', '#E6A23C', '#F56C6C', '#409EFF', '#909399']
  }

  trendChart.setOption(option)
}

// Show AI Report dialog
const showAIReportDialog = () => {
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 1)
  aiReportDateRange.value = [start, end]
  aiReportType.value = 'monthly'
  aiReport.value = null
  aiReportDialogVisible.value = true
}

// Generate AI Report
const generateAIReport = async () => {
  if (!aiReportDateRange.value) {
    ElMessage.warning('请选择日期范围')
    return
  }

  aiReportLoading.value = true
  try {
    const result = await selfInspectionApi.generateAIReport({
      start_date: formatDate(aiReportDateRange.value[0]),
      end_date: formatDate(aiReportDateRange.value[1]),
      report_type: aiReportType.value
    })

    aiReport.value = result
    ElMessage.success('AI报告生成完成')
  } catch (error) {
    ElMessage.error('生成AI报告失败')
    console.error(error)
  } finally {
    aiReportLoading.value = false
  }
}

// Get status tag type
const getStatusType = (status: InspectionStatus): '' | 'success' | 'warning' | 'danger' | 'info' => {
  const types: Record<string, '' | 'success' | 'warning' | 'danger' | 'info'> = {
    pending: 'warning',
    verified: 'success',
    rejected: 'danger'
  }
  return types[status] || 'info'
}

const getStatusText = (status: InspectionStatus): string => {
  const texts: Record<string, string> = {
    pending: '待校验',
    verified: '已校验',
    rejected: '已拒绝'
  }
  return texts[status] || status
}

// Pagination handlers
const handlePageChange = (page: number) => {
  currentPage.value = page
  loadReports()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadReports()
}

// Initialize
onMounted(() => {
  loadReports()
})

// Cleanup
const handleTrendDialogClose = () => {
  if (trendChart) {
    trendChart.dispose()
    trendChart = null
  }
}
</script>

<template>
  <div class="self-inspection-page">
    <!-- Header Card -->
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-title">
            <el-icon><Document /></el-icon>
            <span>文档数据管理</span>
          </div>
          <div class="header-actions">
            <el-button type="primary" @click="showUploadDialog">
              <el-icon><Upload /></el-icon>
              上传检测报告
            </el-button>
            <el-button @click="showTrendDialog">
              <el-icon><TrendCharts /></el-icon>
              趋势分析
            </el-button>
            <el-button @click="showAIReportDialog">
              <el-icon><MagicStick /></el-icon>
              AI运维报告
            </el-button>
          </div>
        </div>
      </template>

      <!-- Filter Section -->
      <el-form :inline="true" class="filter-form">
        <el-form-item label="检测日期">
          <el-date-picker
            v-model="filterDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
            :shortcuts="[
              { text: '最近一周', value: () => { const end = new Date(); const start = new Date(); start.setDate(start.getDate() - 7); return [start, end] } },
              { text: '最近一月', value: () => { const end = new Date(); const start = new Date(); start.setMonth(start.getMonth() - 1); return [start, end] } },
              { text: '最近三月', value: () => { const end = new Date(); const start = new Date(); start.setMonth(start.getMonth() - 3); return [start, end] } }
            ]"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" style="width: 120px" clearable>
            <el-option
              v-for="opt in statusOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadReports">
            <el-icon><Search /></el-icon>
            查询
          </el-button>
          <el-button @click="filterDateRange = null; filterStatus = ''; loadReports()">
            <el-icon><Refresh /></el-icon>
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Reports Table -->
    <el-card class="table-card">
      <el-table
        v-loading="loading"
        :data="reports"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column prop="inspection_date" label="检测日期" width="120" sortable />
        <el-table-column prop="inspection_agency" label="检测机构" min-width="180" show-overflow-tooltip />
        <el-table-column prop="report_number" label="报告编号" width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.report_number || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="original_file_name" label="原始文件" width="180" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.original_file_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="data_count" label="数据项" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small">{{ row.data_count }} 项</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="上传时间" width="170">
          <template #default="{ row }">
            {{ new Date(row.created_at).toLocaleString('zh-CN') }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="openVerifyDialog(row)"
            >
              <el-icon><View /></el-icon>
              查看
            </el-button>
            <el-button
              type="danger"
              link
              size="small"
              @click="deleteReport(row)"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="totalReports"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- Upload Dialog -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传检测报告"
      width="640px"
      destroy-on-close
    >
      <el-form label-width="100px" label-position="left">
        <!-- AI解析模式开关 -->
        <el-form-item label="解析模式">
          <div class="parse-mode-switch">
            <el-switch
              v-model="uploadForm.use_ai_parsing"
              active-text="AI智能解析"
              inactive-text="传统OCR"
              :disabled="uploadLoading"
            />
            <span class="parse-mode-tip">
              {{ uploadForm.use_ai_parsing
                ? 'AI将自动识别检测日期、机构和数据项'
                : '需要手动填写检测日期和机构' }}
            </span>
          </div>
        </el-form-item>

        <el-form-item label="检测报告" required>
          <el-upload
            v-model:file-list="uploadFileList"
            class="upload-area"
            drag
            :auto-upload="false"
            :limit="1"
            accept=".pdf,.jpg,.jpeg,.png"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :disabled="uploadLoading"
          >
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
            <div class="upload-text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="upload-tip">支持 PDF、JPG、PNG 格式，最大 20MB</div>
            </template>
          </el-upload>
        </el-form-item>

        <!-- 传统模式下显示必填字段 -->
        <template v-if="!uploadForm.use_ai_parsing">
          <el-form-item label="检测日期" required>
            <el-date-picker
              v-model="uploadForm.inspection_date"
              type="date"
              placeholder="选择检测日期"
              value-format="YYYY-MM-DD"
              style="width: 100%"
              :disabled="uploadLoading"
            />
          </el-form-item>

          <el-form-item label="检测机构" required>
            <el-input
              v-model="uploadForm.inspection_agency"
              placeholder="请输入检测机构名称"
              :disabled="uploadLoading"
            />
          </el-form-item>
        </template>

        <!-- AI模式下显示可选字段 -->
        <template v-else>
          <el-collapse class="optional-fields">
            <el-collapse-item title="高级选项（可选）">
              <el-form-item label="检测日期">
                <el-date-picker
                  v-model="uploadForm.inspection_date"
                  type="date"
                  placeholder="可选，AI会自动识别"
                  value-format="YYYY-MM-DD"
                  style="width: 100%"
                  :disabled="uploadLoading"
                />
              </el-form-item>
              <el-form-item label="检测机构">
                <el-input
                  v-model="uploadForm.inspection_agency"
                  placeholder="可选，AI会自动识别"
                  :disabled="uploadLoading"
                />
              </el-form-item>
              <el-form-item label="报告编号">
                <el-input
                  v-model="uploadForm.report_number"
                  placeholder="可选"
                  :disabled="uploadLoading"
                />
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </template>

        <!-- 处理进度显示 -->
        <div v-if="ocrProgressVisible" class="ocr-progress">
          <el-steps :active="ocrProgressSteps.filter(s => s.status === 'success').length" finish-status="success" simple>
            <el-step
              v-for="(step, index) in ocrProgressSteps"
              :key="index"
              :title="step.step"
              :status="step.status"
            />
          </el-steps>
        </div>
      </el-form>

      <template #footer>
        <el-button @click="uploadDialogVisible = false" :disabled="uploadLoading">取消</el-button>
        <el-button
          type="primary"
          :loading="uploadLoading"
          :disabled="!canUpload"
          @click="handleUpload"
        >
          {{ uploadLoading ? '正在解析...' : (uploadForm.use_ai_parsing ? 'AI智能解析' : '上传并识别') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- Verify Dialog -->
    <el-dialog
      v-model="verifyDialogVisible"
      title="报告校验"
      width="900px"
      destroy-on-close
    >
      <div v-if="currentReport" class="verify-content">
        <!-- Report Info -->
        <div class="report-info">
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="检测日期">{{ currentReport.inspection_date }}</el-descriptions-item>
            <el-descriptions-item label="检测机构">{{ currentReport.inspection_agency }}</el-descriptions-item>
            <el-descriptions-item label="报告编号">{{ currentReport.report_number || '-' }}</el-descriptions-item>
            <el-descriptions-item label="原始文件">{{ currentReport.original_file_name || '-' }}</el-descriptions-item>
            <el-descriptions-item label="OCR置信度">
              <el-progress
                v-if="currentReport.ocr_confidence"
                :percentage="Math.round(currentReport.ocr_confidence * 100)"
                :stroke-width="8"
                :color="currentReport.ocr_confidence > 0.8 ? '#67c23a' : currentReport.ocr_confidence > 0.5 ? '#e6a23c' : '#f56c6c'"
              />
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="当前状态">
              <el-tag :type="getStatusType(currentReport.status)">
                {{ getStatusText(currentReport.status) }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- Data Items Table -->
        <div class="data-items-section">
          <div class="section-header">
            <span>检测数据项</span>
            <el-button type="primary" size="small" @click="addDataItem">
              + 添加数据项
            </el-button>
          </div>

          <el-table :data="editableDataItems" border size="small" max-height="400">
            <el-table-column label="污染物代码" width="120">
              <template #default="{ row }">
                <el-input v-model="row.pollutant_code" size="small" placeholder="如: w01018" />
              </template>
            </el-table-column>
            <el-table-column label="污染物名称" width="140">
              <template #default="{ row }">
                <el-input v-model="row.pollutant_name" size="small" placeholder="如: COD" />
              </template>
            </el-table-column>
            <el-table-column label="检测值" width="100">
              <template #default="{ row }">
                <el-input-number v-model="row.value" size="small" :precision="3" :min="0" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="单位" width="90">
              <template #default="{ row }">
                <el-input v-model="row.unit" size="small" placeholder="mg/L" />
              </template>
            </el-table-column>
            <el-table-column label="标准限值" width="100">
              <template #default="{ row }">
                <el-input-number v-model="row.standard_limit" size="small" :precision="3" :min="0" controls-position="right" />
              </template>
            </el-table-column>
            <el-table-column label="是否达标" width="90" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.is_compliant" active-color="#67c23a" inactive-color="#f56c6c" />
              </template>
            </el-table-column>
            <el-table-column label="采样点位" min-width="120">
              <template #default="{ row }">
                <el-input v-model="row.sampling_point" size="small" placeholder="选填" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="70" align="center" fixed="right">
              <template #default="{ $index }">
                <el-button type="danger" link size="small" @click="removeDataItem($index)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <template #footer>
        <div class="verify-footer">
          <el-button @click="verifyDialogVisible = false">取消</el-button>
          <el-button
            type="danger"
            :loading="verifyLoading"
            @click="verifyReport('rejected')"
          >
            <el-icon><Close /></el-icon>
            拒绝
          </el-button>
          <el-button
            type="success"
            :loading="verifyLoading"
            @click="verifyReport('verified')"
          >
            <el-icon><Check /></el-icon>
            通过校验
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- Trend Analysis Dialog -->
    <el-dialog
      v-model="trendDialogVisible"
      title="趋势分析"
      width="900px"
      destroy-on-close
      @close="handleTrendDialogClose"
    >
      <div class="trend-content">
        <div class="trend-filter">
          <el-date-picker
            v-model="trendDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 280px"
          />
          <el-button type="primary" :loading="trendLoading" @click="fetchTrendAnalysis">
            <el-icon><TrendCharts /></el-icon>
            生成趋势图
          </el-button>
        </div>

        <div v-if="trendData" class="trend-result">
          <!-- Statistics -->
          <el-row :gutter="16" class="trend-stats">
            <el-col v-for="(stat, code) in trendData.statistics" :key="code" :span="6">
              <el-card shadow="never" class="stat-card">
                <div class="stat-title">{{ stat.name }}</div>
                <div class="stat-values">
                  <span>最小: {{ stat.min.toFixed(2) }}</span>
                  <span>最大: {{ stat.max.toFixed(2) }}</span>
                  <span>平均: {{ stat.avg.toFixed(2) }}</span>
                </div>
              </el-card>
            </el-col>
          </el-row>

          <!-- Chart -->
          <div ref="trendChartRef" class="trend-chart"></div>
        </div>

        <el-empty v-else-if="!trendLoading" description="请选择日期范围并点击生成趋势图" />
      </div>
    </el-dialog>

    <!-- AI Report Dialog -->
    <el-dialog
      v-model="aiReportDialogVisible"
      title="AI运维报告"
      width="800px"
      destroy-on-close
    >
      <div class="ai-report-content">
        <div class="ai-report-filter">
          <el-date-picker
            v-model="aiReportDateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 280px"
          />
          <el-radio-group v-model="aiReportType">
            <el-radio-button value="monthly">月报</el-radio-button>
            <el-radio-button value="quarterly">季报</el-radio-button>
          </el-radio-group>
          <el-button type="primary" :loading="aiReportLoading" @click="generateAIReport">
            <el-icon><MagicStick /></el-icon>
            生成报告
          </el-button>
        </div>

        <div v-if="aiReport" class="ai-report-result">
          <el-card shadow="never" class="report-card">
            <template #header>
              <div class="report-header">
                <span>{{ aiReport.period }} 运维分析报告</span>
                <span class="report-time">生成时间: {{ new Date(aiReport.generated_at).toLocaleString('zh-CN') }}</span>
              </div>
            </template>

            <div class="report-summary">
              <h4>数据概述与分析</h4>
              <div class="summary-content" v-html="aiReport.summary.replace(/\n/g, '<br>')"></div>
            </div>

            <el-divider />

            <div class="report-recommendations">
              <h4>运维建议</h4>
              <ul class="recommendations-list">
                <li v-for="(rec, index) in aiReport.recommendations" :key="index">
                  {{ rec }}
                </li>
              </ul>
            </div>

            <el-divider />

            <div class="report-note">
              <el-icon><Calendar /></el-icon>
              {{ aiReport.data_source_note }}
            </div>
          </el-card>
        </div>

        <el-empty v-else-if="!aiReportLoading" description="请选择日期范围并点击生成报告" />
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.self-inspection-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-form {
  margin-bottom: 0;
}

.table-card {
  flex: 1;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* Upload Dialog */
.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  padding: 40px;
}

.upload-icon {
  font-size: 48px;
  color: #0B1727;
  margin-bottom: 16px;
}

.upload-text {
  color: #606266;
}

.upload-text em {
  color: #0B1727;
  font-style: normal;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

/* Parse mode switch */
.parse-mode-switch {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.parse-mode-tip {
  font-size: 12px;
  color: #909399;
}

/* Optional fields collapse */
.optional-fields {
  margin-top: 8px;
}

.optional-fields :deep(.el-collapse-item__header) {
  font-size: 13px;
  color: #606266;
}

.optional-fields :deep(.el-collapse-item__content) {
  padding-top: 12px;
}

/* OCR Progress */
.ocr-progress {
  margin-top: 24px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.ocr-progress :deep(.el-steps--simple) {
  padding: 0;
}

/* Verify Dialog */
.verify-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.report-info {
  margin-bottom: 8px;
}

.data-items-section {
  flex: 1;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  font-weight: 500;
}

.verify-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* Trend Dialog */
.trend-content {
  min-height: 400px;
}

.trend-filter {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
}

.trend-stats {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
}

.stat-card :deep(.el-card__body) {
  padding: 16px;
}

.stat-title {
  font-weight: 500;
  color: #1D1D1F;
  margin-bottom: 8px;
}

.stat-values {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #606266;
}

.trend-chart {
  height: 400px;
  width: 100%;
}

/* AI Report Dialog */
.ai-report-content {
  min-height: 400px;
}

.ai-report-filter {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 24px;
}

.report-card {
  background: #fafafa;
}

.report-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-time {
  font-size: 12px;
  color: #909399;
}

.report-summary h4,
.report-recommendations h4 {
  margin: 0 0 12px 0;
  color: #1D1D1F;
  font-size: 14px;
}

.summary-content {
  line-height: 1.8;
  color: #606266;
}

.recommendations-list {
  padding-left: 20px;
  margin: 0;
}

.recommendations-list li {
  margin-bottom: 8px;
  line-height: 1.6;
  color: #606266;
}

.report-note {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
}

/* Button Styles */
:deep(.el-button--primary) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
  color: #fff !important;
}

:deep(.el-button--primary:hover),
:deep(.el-button--primary:focus) {
  background-color: #162a3d !important;
  border-color: #162a3d !important;
}

:deep(.el-button--primary.is-disabled),
:deep(.el-button--primary.is-disabled:hover) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
  opacity: 0.5;
}

:deep(.el-button--success) {
  background-color: #1D6F42 !important;
  border-color: #1D6F42 !important;
}

:deep(.el-button--success:hover),
:deep(.el-button--success:focus) {
  background-color: #258B52 !important;
  border-color: #258B52 !important;
}

:deep(.el-button--default:hover) {
  border-color: #0B1727 !important;
  color: #0B1727 !important;
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background-color: #0B1727 !important;
  border-color: #0B1727 !important;
  box-shadow: -1px 0 0 0 #0B1727 !important;
}

/* Progress bar color */
:deep(.el-progress-bar__inner) {
  transition: width 0.3s;
}
</style>
