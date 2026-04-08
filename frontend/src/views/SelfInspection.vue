<script setup lang="ts">
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { AxiosError } from 'axios'
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
  Refresh,
  OfficeBuilding,
  InfoFilled
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
  type OpsBriefListItem,
  type InspectionStatus
} from '@/api/selfInspection'
import { organizationApi, type Organization } from '@/api/organizations'
import { useAuthStore } from '@/stores/auth'
import DeviceOnlineMetricsCard from '@/components/DeviceOnlineMetricsCard.vue'
import { POLLUTANT_MAP, generateGroupedPollutantOptions } from '@/config/pollutants'

// ============== Auth & Organization ==============
const authStore = useAuthStore()
const canEditDocuments = computed(() => authStore.canEditDocuments)
const canDeleteDocuments = computed(() => authStore.canDeleteDocuments)
const organizations = ref<Organization[]>([])
const canSelectTargetOrg = computed(() => authStore.user?.is_superadmin === true || authStore.user?.role === 'doc_editor')
const selectedOrgId = ref<string>('')  // 页面级组织选择器（超管/文案用）

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
  use_ai_parsing: true,  // AI智能解析开关
  target_org_id: ''  // 目标组织ID（超级管理员专用）
})
const uploadFileList = ref<UploadFile[]>()
const ocrProgressVisible = ref(false)
const ocrProgressSteps = ref<{ step: string; status: 'process' | 'success' | 'error' }[]>([])
const MAX_UPLOAD_SIZE_BYTES = 19 * 1024 * 1024
const RECOMMENDED_UPLOAD_SIZE_BYTES = 19 * 1024 * 1024

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
const aiReportIncludeFlow = ref(false)
const aiReportIncludeAirOnline = ref(false)
const aiReportCalculateLoad = ref(false)
const opsBriefGenerating = ref(false)
const opsBriefHistoryLoading = ref(false)
const opsBriefHistory = ref<OpsBriefListItem[]>([])

// ============== Computed ==============
const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待校验' },
  { value: 'verified', label: '已校验' },
  { value: 'rejected', label: '已拒绝' }
]

// Pollutant options for dropdown (grouped by category)
const pollutantOptions = computed(() => generateGroupedPollutantOptions())

// Handle pollutant selection - auto fill name, unit, etc.
const handlePollutantSelect = (code: string, item: SelfInspectionDataItem) => {
  const info = POLLUTANT_MAP[code.toLowerCase()]
  if (info) {
    item.pollutant_code = code
    item.pollutant_name = info.name
    item.unit = info.unit
    // Note: standard_limit needs to be set based on discharge standards,
    // which varies by industry. For now, keep it editable.
  }
}

// Superscript number mapping for scientific notation
const superscriptMap: Record<string, string> = {
  '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
  '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
  '-': '⁻', '+': '⁺'
}

// Convert regular numbers to superscript
const toSuperscript = (num: string): string => {
  return num.split('').map(c => superscriptMap[c] || c).join('')
}

// Handle value input - auto convert scientific notation formats
// Supports: "4.0E2", "4.0e2", "4.0*10^2", "4.0×10^2", "4.0x10^2"
// Converts to: "4.0×10²"
const handleValueInput = (val: string, item: SelfInspectionDataItem, field: 'value' | 'standard_limit') => {
  if (!val) return

  // Pattern 1: "4.0E2" or "4.0e2" -> "4.0×10²"
  const eNotation = val.match(/^([\d.]+)[Ee]([+-]?\d+)$/)
  if (eNotation) {
    const [, mantissa, exp] = eNotation
    item[field] = `${mantissa}×10${toSuperscript(exp)}`
    return
  }

  // Pattern 2: "4.0*10^2" or "4.0×10^2" or "4.0x10^2" -> "4.0×10²"
  const caretNotation = val.match(/^([\d.]+)[*×xX]10\^([+-]?\d+)$/)
  if (caretNotation) {
    const [, mantissa, exp] = caretNotation
    item[field] = `${mantissa}×10${toSuperscript(exp)}`
    return
  }

  // Pattern 3: "4.0*10**2" -> "4.0×10²"
  const doubleStarNotation = val.match(/^([\d.]+)[*×xX]10\*\*([+-]?\d+)$/)
  if (doubleStarNotation) {
    const [, mantissa, exp] = doubleStarNotation
    item[field] = `${mantissa}×10${toSuperscript(exp)}`
    return
  }
}

// AI智能解析模式下，只需要文件；传统模式需要填写日期和机构
// 超级管理员还需要选择目标企业
const canUpload = computed(() => {
  // 平台人员（超管/文案）必须选择目标企业
  if (canSelectTargetOrg.value && !uploadForm.target_org_id) {
    return false
  }
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
    // 平台人员选择了企业时，按企业过滤
    if (canSelectTargetOrg.value && selectedOrgId.value) {
      params.target_org_id = selectedOrgId.value
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
    if (file.raw.size > MAX_UPLOAD_SIZE_BYTES) {
      ElMessage.warning('文件大小不能超过 19MB（云托管网关限制）')
      uploadFileList.value = []
      return
    }
    if (file.raw.size > RECOMMENDED_UPLOAD_SIZE_BYTES) {
      ElMessage.warning('文件接近网关上限，建议压缩到 19MB 以内，避免上传时报 Network Error')
    }
    uploadForm.file = file.raw
  }
}

const handleFileRemove = () => {
  uploadForm.file = null
  uploadFileList.value = []
}

// Load organizations for super admin
const loadOrganizations = async () => {
  if (!canSelectTargetOrg.value) return
  try {
    organizations.value = await organizationApi.list()
  } catch (error) {
    console.error('Failed to load organizations:', error)
  }
}

// Show upload dialog
const showUploadDialog = async () => {
  uploadForm.file = null
  uploadForm.inspection_date = ''
  uploadForm.inspection_agency = ''
  uploadForm.report_number = ''
  uploadForm.use_ai_parsing = true
  // 自动填充页面级选择的组织
  uploadForm.target_org_id = selectedOrgId.value || ''
  uploadFileList.value = []
  ocrProgressVisible.value = false
  ocrProgressSteps.value = []

  // 平台人员需要加载组织列表
  if (canSelectTargetOrg.value && organizations.value.length === 0) {
    await loadOrganizations()
  }

  uploadDialogVisible.value = true
}

// Upload and OCR with AI parsing
const handleUpload = async () => {
  if (!canUpload.value || !uploadForm.file) {
    if (canSelectTargetOrg.value && !uploadForm.target_org_id) {
      ElMessage.warning('请先选择目标企业')
    } else {
      ElMessage.warning(uploadForm.use_ai_parsing ? '请选择文件' : '请填写完整信息并选择文件')
    }
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
      uploadForm.use_ai_parsing,
      uploadForm.target_org_id || undefined  // 超级管理员指定的目标企业
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
    let errMsg = error instanceof Error ? error.message : '上传失败'
    const axiosError = error as AxiosError<{ detail?: string }>

    if (axiosError?.response?.status === 413) {
      errMsg = '上传失败：文件或请求体过大，请压缩后重试（建议 19MB 以内）'
    } else if (axiosError?.code === 'ECONNABORTED') {
      errMsg = '上传超时：OCR/AI 处理时间较长，请稍后重试或减小文件体积'
    } else if (!axiosError?.response && uploadForm.file && uploadForm.file.size > RECOMMENDED_UPLOAD_SIZE_BYTES) {
      errMsg = '上传失败：可能触发网关大小限制（浏览器可能显示为 CORS/Network Error），请压缩到 19MB 以内重试'
    }

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
      end_date: formatDate(trendDateRange.value[1]),
      target_org_id: selectedOrgId.value || undefined  // 超级管理员按企业过滤
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

const validateAIReportQuery = () => {
  if (!aiReportDateRange.value) {
    ElMessage.warning('请选择日期范围')
    return false
  }

  if (canSelectTargetOrg.value && aiReportIncludeFlow.value && !selectedOrgId.value) {
    ElMessage.warning('整合流量数据需要先在页面上方选择企业')
    return false
  }
  if (canSelectTargetOrg.value && aiReportIncludeAirOnline.value && !selectedOrgId.value) {
    ElMessage.warning('整合在线监测指标需要先在页面上方选择企业')
    return false
  }
  return true
}

const loadOpsBriefHistory = async () => {
  opsBriefHistoryLoading.value = true
  try {
    const result = await selfInspectionApi.listOpsBriefHistory({
      target_org_id: selectedOrgId.value || undefined,
      page: 1,
      page_size: 20
    })
    opsBriefHistory.value = result.items
  } catch (error) {
    console.error('Failed to load ops brief history:', error)
  } finally {
    opsBriefHistoryLoading.value = false
  }
}

// Show AI Report dialog
const showAIReportDialog = async () => {
  const end = new Date()
  const start = new Date()
  start.setMonth(start.getMonth() - 1)
  aiReportDateRange.value = [start, end]
  aiReportType.value = 'monthly'
  aiReport.value = null
  // 默认开启整合流量数据：企业用户直接可用；平台人员若未选企业则默认关闭避免误操作
  aiReportIncludeFlow.value = canSelectTargetOrg.value ? Boolean(selectedOrgId.value) : true
  aiReportIncludeAirOnline.value = true
  aiReportCalculateLoad.value = false
  aiReportDialogVisible.value = true

  await loadOpsBriefHistory()
}

// Generate AI Report
const generateAIReport = async () => {
  if (!validateAIReportQuery()) return
  const dateRange = aiReportDateRange.value
  if (!dateRange) return

  aiReportLoading.value = true
  try {
    const result = await selfInspectionApi.generateAIReport({
      start_date: formatDate(dateRange[0]),
      end_date: formatDate(dateRange[1]),
      report_type: aiReportType.value,
      include_flow_data: aiReportIncludeFlow.value,
      include_air_online_data: aiReportIncludeAirOnline.value,
      calculate_pollutant_load: aiReportCalculateLoad.value,
      target_org_id: selectedOrgId.value || undefined  // 平台人员按企业过滤
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

const generateAndArchiveOpsBrief = async () => {
  if (aiReportType.value !== 'monthly') {
    ElMessage.warning('运维简报仅支持月度类型，请切换为“月报”')
    return
  }
  if (canSelectTargetOrg.value && !selectedOrgId.value) {
    ElMessage.warning('请先选择目标企业后再生成月度运维简报')
    return
  }
  if (!validateAIReportQuery()) return
  const dateRange = aiReportDateRange.value
  if (!dateRange) return

  opsBriefGenerating.value = true
  try {
    const result = await selfInspectionApi.generateOpsBrief({
      start_date: formatDate(dateRange[0]),
      end_date: formatDate(dateRange[1]),
      include_flow_data: aiReportIncludeFlow.value,
      include_air_online_data: true,
      calculate_pollutant_load: aiReportCalculateLoad.value,
      target_org_id: selectedOrgId.value || undefined
    })

    aiReport.value = result
    ElMessage.success('月度运维简报已生成并归档')
    await loadOpsBriefHistory()
  } catch (error) {
    ElMessage.error('生成运维简报失败')
    console.error(error)
  } finally {
    opsBriefGenerating.value = false
  }
}

const viewArchivedOpsBrief = async (briefId: string) => {
  opsBriefGenerating.value = true
  try {
    const detail = await selfInspectionApi.getOpsBrief(briefId)
    aiReport.value = detail
  } catch (error) {
    ElMessage.error('加载归档简报失败')
    console.error(error)
  } finally {
    opsBriefGenerating.value = false
  }
}

const downloadOpsBriefPdf = async (briefId: string) => {
  try {
    const { blob, filename } = await selfInspectionApi.downloadOpsBriefPdf(briefId)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch (error) {
    ElMessage.error('下载简报PDF失败')
    console.error(error)
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
onMounted(async () => {
  loadReports()
  // 平台人员页面加载时获取组织列表
  if (canSelectTargetOrg.value) {
    await loadOrganizations()
  }
})

// 监听组织选择变化，超级管理员切换企业时重新加载数据
watch(selectedOrgId, () => {
  // 重置分页到第一页
  currentPage.value = 1
  // 重新加载报告列表
  loadReports()
  if (aiReportDialogVisible.value) {
    loadOpsBriefHistory()
  }
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
            <!-- 平台人员：页面级组织选择器 -->
            <el-select
              v-if="canSelectTargetOrg"
              v-model="selectedOrgId"
              placeholder="选择企业"
              style="width: 200px; margin-right: 12px"
              clearable
              filterable
            >
              <template #prefix>
                <el-icon><OfficeBuilding /></el-icon>
              </template>
              <el-option
                v-for="org in organizations"
                :key="org.id"
                :label="org.name"
                :value="org.id"
              />
            </el-select>
            <el-button v-if="canEditDocuments" type="primary" @click="showUploadDialog">
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

    <!-- Online Metrics Card (Data from DAQ devices - read only) -->
    <DeviceOnlineMetricsCard
      :hours="24"
      :target-org-id="selectedOrgId"
    />

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
              v-if="canDeleteDocuments"
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
        <!-- 平台人员：选择目标企业 -->
        <el-form-item v-if="canSelectTargetOrg" label="目标企业" required>
          <el-select
            v-model="uploadForm.target_org_id"
            placeholder="请选择要上传报告的企业"
            style="width: 100%"
            :disabled="uploadLoading"
            filterable
          >
            <el-option
              v-for="org in organizations"
              :key="org.id"
              :label="org.name"
              :value="org.id"
            >
              <span>{{ org.name }}</span>
              <span style="color: #909399; font-size: 12px; margin-left: 8px;">{{ org.code }}</span>
            </el-option>
          </el-select>
          <div class="form-tip">
            <el-icon><OfficeBuilding /></el-icon>
            作为环保管家，您可以为不同企业上传自检报告
          </div>
        </el-form-item>

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
              <div class="upload-tip">支持 PDF、JPG、PNG 格式，最大 19MB</div>
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
            <el-button v-if="canEditDocuments" type="primary" size="small" @click="addDataItem">
              + 添加数据项
            </el-button>
          </div>

          <el-table :data="editableDataItems" border size="small" max-height="400">
            <el-table-column label="污染物" width="200">
              <template #default="{ row }">
                <el-select
                  v-model="row.pollutant_code"
                  size="small"
                  filterable
                  placeholder="搜索或选择"
                  style="width: 100%"
                  :disabled="!canEditDocuments"
                  @change="(val: string) => handlePollutantSelect(val, row)"
                >
                  <el-option-group
                    v-for="group in pollutantOptions"
                    :key="group.label"
                    :label="group.label"
                  >
                    <el-option
                      v-for="opt in group.options"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-option-group>
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="污染物名称" width="100">
              <template #default="{ row }">
                <span class="pollutant-name">{{ row.pollutant_name || '-' }}</span>
              </template>
            </el-table-column>
            <el-table-column label="检测值" width="120">
              <template #default="{ row }">
                <el-input
                  v-model="row.value"
                  size="small"
                  placeholder="如: 4.0×10²"
                  :disabled="!canEditDocuments"
                  @input="(val: string) => handleValueInput(val, row, 'value')"
                />
              </template>
            </el-table-column>
            <el-table-column label="单位" width="90">
              <template #default="{ row }">
                <el-input v-model="row.unit" size="small" placeholder="mg/L" :disabled="!canEditDocuments" />
              </template>
            </el-table-column>
            <el-table-column label="标准限值" width="120">
              <template #default="{ row }">
                <el-input
                  v-model="row.standard_limit"
                  size="small"
                  placeholder="如: 4.0×10²"
                  :disabled="!canEditDocuments"
                  @input="(val: string) => handleValueInput(val, row, 'standard_limit')"
                />
              </template>
            </el-table-column>
            <el-table-column label="是否达标" width="90" align="center">
              <template #default="{ row }">
                <el-switch v-model="row.is_compliant" active-color="#67c23a" inactive-color="#f56c6c" :disabled="!canEditDocuments" />
              </template>
            </el-table-column>
            <el-table-column label="采样点位" min-width="120">
              <template #default="{ row }">
                <el-input v-model="row.sampling_point" size="small" placeholder="选填" :disabled="!canEditDocuments" />
              </template>
            </el-table-column>
            <el-table-column v-if="canEditDocuments" label="操作" width="70" align="center" fixed="right">
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
          <el-button @click="verifyDialogVisible = false">{{ canEditDocuments ? '取消' : '关闭' }}</el-button>
          <template v-if="canEditDocuments">
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
          </template>
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
          <el-button type="success" :loading="opsBriefGenerating" @click="generateAndArchiveOpsBrief">
            一键生成并归档简报
          </el-button>
        </div>

        <!-- Flow Data Integration Options -->
        <div class="flow-options">
          <el-checkbox v-model="aiReportIncludeFlow" :disabled="aiReportLoading">
            整合瞬时流量数据
          </el-checkbox>
          <el-checkbox v-model="aiReportIncludeAirOnline" :disabled="aiReportLoading">
            整合大气污染物在线指标
          </el-checkbox>
          <el-checkbox
            v-model="aiReportCalculateLoad"
            :disabled="aiReportLoading || !aiReportIncludeFlow"
          >
            计算污染负荷
          </el-checkbox>
          <div class="flow-options-tip">
            <el-icon><InfoFilled /></el-icon>
            <span>流量数据用于负荷计算；大气在线指标用于标准对照解读</span>
          </div>
        </div>

        <el-card shadow="never" class="brief-history-card">
          <template #header>
            <div class="brief-history-header">
              <span>运维简报历史归档</span>
              <el-button text type="primary" @click="loadOpsBriefHistory">刷新</el-button>
            </div>
          </template>

          <el-table :data="opsBriefHistory" size="small" v-loading="opsBriefHistoryLoading" max-height="220">
            <el-table-column prop="title" label="简报标题" min-width="220" show-overflow-tooltip />
            <el-table-column label="周期" min-width="190">
              <template #default="{ row }">
                {{ row.start_date }} 至 {{ row.end_date }}
              </template>
            </el-table-column>
            <el-table-column label="生成时间" min-width="170">
              <template #default="{ row }">
                {{ new Date(row.generated_at).toLocaleString('zh-CN') }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="170" fixed="right">
              <template #default="{ row }">
                <el-button text type="primary" @click="viewArchivedOpsBrief(row.id)">查看</el-button>
                <el-button text type="success" @click="downloadOpsBriefPdf(row.id)">PDF</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <div v-if="aiReport" class="ai-report-result">
          <el-card shadow="never" class="report-card">
            <template #header>
              <div class="report-header">
                <span>{{ aiReport.period }} 运维分析报告</span>
                <span class="report-time">生成时间: {{ new Date(aiReport.generated_at).toLocaleString('zh-CN') }}</span>
              </div>
            </template>

            <template v-if="aiReport.flow_data">
              <div class="report-flow">
                <h4>流量数据摘要（数采仪）</h4>
                <el-row :gutter="12">
                  <el-col :span="8">
                    <el-tag type="info" size="small">平均流量: {{ aiReport.flow_data.avg_flow.toFixed(2) }} L/s</el-tag>
                  </el-col>
                  <el-col :span="8">
                    <el-tag type="info" size="small">日总流量: {{ (aiReport.flow_data.daily_volume_m3 ?? aiReport.flow_data.total_volume).toFixed(2) }} m³</el-tag>
                  </el-col>
                  <el-col :span="8">
                    <el-tag type="info" size="small">数据点: {{ aiReport.flow_data.data_points_count }}</el-tag>
                  </el-col>
                </el-row>
              </div>
              <el-divider />
            </template>

            <template v-if="aiReport.online_data && aiReport.online_data.pollutants && aiReport.online_data.pollutants.length > 0">
              <div class="report-online">
                <h4>大气在线监测指标概览（数采仪）</h4>
                <el-collapse>
                  <el-collapse-item
                    :title="`查看指标统计（${aiReport.online_data.pollutants.length}项）`"
                    name="online"
                  >
                    <ul class="online-metrics-list">
                      <li v-for="p in aiReport.online_data.pollutants.slice(0, 12)" :key="p.pollutant_code">
                        {{ p.pollutant_name }}（{{ p.pollutant_code }}）：均值 {{ p.avg ?? '-' }}{{ p.unit || '' }}
                        <template v-if="p.standard_limit !== null && p.standard_limit !== undefined">，参考限值 {{ p.standard_limit }}{{ p.unit || '' }}</template>
                        ，范围 {{ p.min ?? '-' }}-{{ p.max ?? '-' }}{{ p.unit || '' }}（{{ p.count }}点 / {{ p.device_count }}设备）
                      </li>
                    </ul>
                    <div v-if="aiReport.online_data.note" class="online-metrics-note">
                      {{ aiReport.online_data.note }}
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
              <el-divider />
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

            <!-- Pollutant Loads Section -->
            <template v-if="aiReport.pollutant_loads">
              <el-divider />
              <div class="pollutant-loads-section">
                <h4>污染负荷计算</h4>
                <div class="loads-source-info">
                  <el-tag type="info" size="small">流量来源: {{ aiReport.pollutant_loads.flow_source }}</el-tag>
                  <el-tag type="info" size="small">浓度来源: {{ aiReport.pollutant_loads.concentration_source }}</el-tag>
                </div>
                <div class="loads-summary">
                  <span>平均流量: <strong>{{ aiReport.pollutant_loads.avg_flow_l_s.toFixed(2) }} L/s</strong></span>
                  <span>日排放量: <strong>{{ aiReport.pollutant_loads.daily_volume_m3.toFixed(2) }} m³/d</strong></span>
                </div>
                <el-table :data="Object.values(aiReport.pollutant_loads.pollutant_loads)" size="small" border>
                  <el-table-column prop="name" label="污染物" width="100" />
                  <el-table-column prop="avg_concentration_mg_l" label="平均浓度(mg/L)" width="130">
                    <template #default="{ row }">{{ row.avg_concentration_mg_l.toFixed(3) }}</template>
                  </el-table-column>
                  <el-table-column prop="daily_load_kg" label="日负荷(kg/d)" width="120">
                    <template #default="{ row }">{{ row.daily_load_kg.toFixed(3) }}</template>
                  </el-table-column>
                  <el-table-column prop="monthly_load_kg" label="月负荷(kg/月)" width="130">
                    <template #default="{ row }">{{ row.monthly_load_kg.toFixed(2) }}</template>
                  </el-table-column>
                  <el-table-column prop="formula" label="计算公式" min-width="200" show-overflow-tooltip />
                </el-table>
                <div class="loads-note">
                  <el-icon><InfoFilled /></el-icon>
                  {{ aiReport.pollutant_loads.note }}
                </div>
              </div>
            </template>

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
.form-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
}

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

/* Pollutant name display */
.pollutant-name {
  color: #606266;
  font-size: 13px;
}

/* Pollutant select styles */
:deep(.el-select-dropdown__item) {
  font-size: 13px;
}

:deep(.el-select-group__title) {
  font-size: 12px;
  color: #909399;
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
  margin-bottom: 16px;
}

.flow-options {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 24px;
}

.flow-options-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
  margin-left: auto;
}

.brief-history-card {
  margin-bottom: 16px;
}

.brief-history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 500;
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

.report-flow,
.report-online {
  margin-bottom: 8px;
}

.online-metrics-list {
  padding-left: 18px;
  margin: 8px 0 0 0;
  color: #606266;
}

.online-metrics-list li {
  margin-bottom: 6px;
  line-height: 1.6;
}

.online-metrics-note {
  margin-top: 10px;
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

/* Pollutant Loads Section */
.pollutant-loads-section h4 {
  margin: 0 0 12px 0;
  color: #1D1D1F;
  font-size: 14px;
}

.loads-source-info {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.loads-summary {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
  color: #606266;
}

.loads-summary strong {
  color: #0B1727;
}

.loads-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
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
