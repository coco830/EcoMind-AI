<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus/es/components/message/index'
import { regulatorApi, type RegulatorBrief } from '@/api/regulator'

const period = ref<'daily' | 'monthly'>('daily')
const targetDate = ref<string>(getYesterday())
const targetMonth = ref<string>(getCurrentMonth())
const regionCode = ref('')
const parkCode = ref('')
const loading = ref(false)
const downloadLoading = ref(false)
const brief = ref<RegulatorBrief | null>(null)

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

const canGenerate = computed(() => {
  if (period.value === 'daily') return !!targetDate.value
  return !!targetMonth.value
})

const quotaLabel = computed(() => {
  if (!brief.value) return ''
  const quota = brief.value.quota
  if (period.value === 'monthly') {
    return `本月剩余生成次数：${quota.remaining}/${quota.limit}`
  }
  return `今日剩余生成次数：${quota.remaining}/${quota.limit}`
})

const insufficientIndustries = computed(() => {
  if (!brief.value) return ''
  const list = brief.value.industry_distribution
    .filter(item => item.insufficient)
    .map(item => item.industry)
  return list.length ? list.join('、') : ''
})

const riskTagType = (level: string) => {
  switch (level) {
    case 'L5':
      return 'danger'
    case 'L4':
      return 'warning'
    case 'L3':
      return 'info'
    case 'L2':
      return 'success'
    case 'L1':
    default:
      return 'success'
  }
}

const handleGenerate = async () => {
  if (!canGenerate.value) {
    ElMessage.warning('请选择统计周期')
    return
  }

  loading.value = true
  try {
    if (period.value === 'daily') {
      brief.value = await regulatorApi.getBrief({
        period: 'daily',
        target_date: targetDate.value,
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      })
    } else {
      const [yearStr, monthStr] = targetMonth.value.split('-')
      brief.value = await regulatorApi.getBrief({
        period: 'monthly',
        year: Number(yearStr),
        month: Number(monthStr),
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      })
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '简报生成失败')
  } finally {
    loading.value = false
  }
}

const handleDownload = async (format: 'excel' | 'pdf') => {
  if (!brief.value) {
    ElMessage.warning('请先生成简报')
    return
  }
  downloadLoading.value = true
  try {
    if (period.value === 'daily') {
      await regulatorApi.downloadBrief({
        period: 'daily',
        target_date: targetDate.value,
        format,
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      })
    } else {
      const [yearStr, monthStr] = targetMonth.value.split('-')
      await regulatorApi.downloadBrief({
        period: 'monthly',
        year: Number(yearStr),
        month: Number(monthStr),
        format,
        region_code: regionCode.value || undefined,
        park_code: parkCode.value || undefined
      })
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || '简报导出失败')
  } finally {
    downloadLoading.value = false
  }
}
</script>

<template>
  <div class="regulator-brief">
    <el-card class="filter-card">
      <template #header>
        <div class="card-header">AI监管简报</div>
      </template>

      <div class="form-row">
        <el-select v-model="period" placeholder="简报周期" style="width: 160px">
          <el-option label="日简报" value="daily" />
          <el-option label="月简报" value="monthly" />
        </el-select>

        <el-date-picker
          v-if="period === 'daily'"
          v-model="targetDate"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
          format="YYYY-MM-DD"
        />
        <el-date-picker
          v-else
          v-model="targetMonth"
          type="month"
          placeholder="选择月份"
          value-format="YYYY-MM"
          format="YYYY-MM"
        />

        <el-input v-model="regionCode" placeholder="区县编码 (可选)" style="width: 160px" />
        <el-input v-model="parkCode" placeholder="园区编码 (可选)" style="width: 160px" />
      </div>

      <div class="actions">
        <el-button type="primary" :loading="loading" @click="handleGenerate">
          生成简报
        </el-button>
        <el-button :loading="downloadLoading" @click="handleDownload('excel')">
          导出 Excel
        </el-button>
        <el-button :loading="downloadLoading" @click="handleDownload('pdf')">
          导出 PDF
        </el-button>
        <span v-if="quotaLabel" class="quota-text">{{ quotaLabel }}</span>
      </div>

      <div class="note">
        日简报每天最多 3 次，月简报每月最多 1 次。简报仅展示聚合统计结果。
      </div>
    </el-card>

    <template v-if="brief">
      <el-row :gutter="16" class="section-row">
        <el-col :span="16">
          <el-card>
            <template #header>
              <div class="card-header">总体态势</div>
            </template>
            <div class="summary-text">{{ brief.summary_text }}</div>
            <ul class="highlight-list" v-if="brief.highlights.length">
              <li v-for="item in brief.highlights" :key="item">{{ item }}</li>
            </ul>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card class="metrics-card">
            <template #header>
              <div class="card-header">
                运行质量
                <el-tag :type="riskTagType(brief.overview.risk_level)" size="small">
                  {{ brief.overview.risk_level }}
                </el-tag>
              </div>
            </template>
            <div class="metrics-grid">
              <div class="metric-item">
                <div class="metric-label">企业数</div>
                <div class="metric-value">{{ brief.overview.enterprise_count }}</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">设备数</div>
                <div class="metric-value">{{ brief.overview.device_count }}</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">在线率</div>
                <div class="metric-value">{{ brief.overview.online_rate }}%</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">离线率</div>
                <div class="metric-value">{{ brief.overview.offline_rate }}%</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">超标率</div>
                <div class="metric-value">{{ brief.overview.exceed_rate }}%</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">无效率</div>
                <div class="metric-value">{{ brief.overview.invalid_rate }}%</div>
              </div>
              <div class="metric-item">
                <div class="metric-label">报警率</div>
                <div class="metric-value">{{ brief.overview.alarm_rate }}%</div>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="section-row">
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">区域态势 TOP5</div>
            </template>
            <el-table :data="brief.top_regions" size="small" style="width: 100%">
              <el-table-column prop="name" label="区域" min-width="120" />
              <el-table-column prop="risk_level" label="等级" width="80">
                <template #default="{ row }">
                  <el-tag :type="riskTagType(row.risk_level)" size="small">
                    {{ row.risk_level }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="risk_score" label="风险分" width="90" />
              <el-table-column prop="enterprise_count" label="企业数" width="90" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">行业态势 TOP5</div>
            </template>
            <el-table :data="brief.top_industries" size="small" style="width: 100%">
              <el-table-column prop="code" label="行业" min-width="120" />
              <el-table-column prop="risk_level" label="等级" width="80">
                <template #default="{ row }">
                  <el-tag :type="riskTagType(row.risk_level)" size="small">
                    {{ row.risk_level }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="risk_score" label="风险分" width="90" />
              <el-table-column prop="enterprise_count" label="企业数" width="90" />
            </el-table>
            <div v-if="insufficientIndustries" class="insufficient-note">
              样本不足行业：{{ insufficientIndustries }}
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" class="section-row">
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">一致性评估</div>
            </template>
            <div class="consistency-grid">
              <div class="consistency-item">
                <div class="consistency-label">高一致</div>
                <div class="consistency-value">{{ brief.consistency.summary.high }}</div>
              </div>
              <div class="consistency-item">
                <div class="consistency-label">中一致</div>
                <div class="consistency-value">{{ brief.consistency.summary.medium }}</div>
              </div>
              <div class="consistency-item">
                <div class="consistency-label">低一致</div>
                <div class="consistency-value">{{ brief.consistency.summary.low }}</div>
              </div>
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>
              <div class="card-header">监管建议</div>
            </template>
            <ul class="suggestion-list">
              <li v-for="item in brief.suggestions" :key="item">{{ item }}</li>
            </ul>
          </el-card>
        </el-col>
      </el-row>

      <div class="data-note">{{ brief.data_note }}</div>
    </template>
  </div>
</template>

<style scoped>
.regulator-brief {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.card-header {
  font-weight: 600;
  color: #1d1d1f;
  display: flex;
  align-items: center;
  gap: 8px;
}

.form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.quota-text {
  font-size: 12px;
  color: #4b5563;
}

.note {
  margin-top: 12px;
  font-size: 12px;
  color: #6b7280;
}

.section-row {
  width: 100%;
}

.summary-text {
  font-size: 14px;
  color: #1f2937;
  margin-bottom: 8px;
}

.highlight-list,
.suggestion-list {
  padding-left: 18px;
  margin: 0;
  color: #374151;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.metrics-card :deep(.el-card__body) {
  padding-top: 8px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.metric-item {
  background: #f9fafb;
  border-radius: 8px;
  padding: 10px 12px;
  border: 1px solid #eef2f7;
}

.metric-label {
  font-size: 12px;
  color: #6b7280;
}

.metric-value {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  margin-top: 4px;
}

.insufficient-note {
  margin-top: 10px;
  font-size: 12px;
  color: #b45309;
}

.consistency-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.consistency-item {
  text-align: center;
  background: #f9fafb;
  border-radius: 8px;
  padding: 12px 8px;
  border: 1px solid #eef2f7;
}

.consistency-label {
  font-size: 12px;
  color: #6b7280;
}

.consistency-value {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  margin-top: 6px;
}

.data-note {
  font-size: 12px;
  color: #6b7280;
  margin-top: -4px;
}
</style>
