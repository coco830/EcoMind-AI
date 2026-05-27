<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index'
import { regulatorApi } from '@/api/regulator'
import RegulatorBrief from '@/views/RegulatorBrief.vue'

const reportType = ref<'daily' | 'monthly'>('daily')
const reportDate = ref<string>(getYesterday())
const reportMonth = ref<string>(getCurrentMonth())
const regionCode = ref('')
const parkCode = ref('')
const downloadLoading = ref(false)

function getYesterday(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}

function getCurrentMonth(): string {
  const d = new Date()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  return `${d.getFullYear()}-${month}`
}

const canDownload = computed(() => {
  if (reportType.value === 'daily') return !!reportDate.value
  return !!reportMonth.value
})

const handleDownload = async (format: 'excel' | 'pdf') => {
  if (!canDownload.value) {
    ElMessage.warning('请选择报表日期')
    return
  }

  downloadLoading.value = true
  try {
    if (reportType.value === 'daily') {
      await regulatorApi.downloadReport({
        report_type: 'daily',
        target_date: reportDate.value,
        format,
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      })
    } else {
      const [yearStr, monthStr] = reportMonth.value.split('-')
      const year = Number(yearStr)
      const month = Number(monthStr)
      await regulatorApi.downloadReport({
        report_type: 'monthly',
        year,
        month,
        format,
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      })
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '报表导出失败')
  } finally {
    downloadLoading.value = false
  }
}
</script>

<template>
  <div class="regulator-documents">
    <div class="page-title">监管文档</div>
    <RegulatorBrief />
    <el-card class="report-card">
      <template #header>
        <div class="card-header">监管报表导出</div>
      </template>

      <div class="form-row">
        <el-select v-model="reportType" placeholder="报表类型" style="width: 160px">
          <el-option label="日报" value="daily" />
          <el-option label="月报" value="monthly" />
        </el-select>

        <el-date-picker
          v-if="reportType === 'daily'"
          v-model="reportDate"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
          format="YYYY-MM-DD"
        />
        <el-date-picker
          v-else
          v-model="reportMonth"
          type="month"
          placeholder="选择月份"
          value-format="YYYY-MM"
          format="YYYY-MM"
        />

        <el-input v-model="regionCode" placeholder="区县编码 (可选)" style="width: 160px" />
        <el-input v-model="parkCode" placeholder="园区编码 (可选)" style="width: 160px" />
      </div>

      <div class="download-actions">
        <el-button
          type="primary"
          :loading="downloadLoading"
          @click="handleDownload('excel')"
        >
          导出 Excel
        </el-button>
        <el-button
          type="default"
          :loading="downloadLoading"
          @click="handleDownload('pdf')"
        >
          导出 PDF
        </el-button>
      </div>

      <div class="note">
        报表仅包含聚合统计数据，不展示企业级明细。
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.regulator-documents {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.card-header {
  font-weight: 600;
  color: #1d1d1f;
}

.form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.download-actions {
  display: flex;
  gap: 12px;
}

.note {
  margin-top: 16px;
  font-size: 12px;
  color: #6b7280;
}
</style>
