<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import MarkdownIt from 'markdown-it'
import { useAuthStore } from '@/stores/auth'
import { apiBasePath } from '@/api/request'

// Props
const props = defineProps<{
  deviceId: string
  deviceName: string
  pollutant?: string  // Optional - if not provided, use comprehensive analysis
}>()

interface VideoEvidenceFragment {
  event_id: string
  occurred_at: string
  channel_name: string
  point_type_label: string
  title: string
  risk_label: string
  risk_score: number
  associated_data_summary: string
  suggested_action: string
  snapshot_uri?: string | null
  clip_uri?: string | null
}

interface VideoRiskAssessment {
  overall_risk_level: string
  overall_risk_label: string
  overall_risk_score: number
  summary: string
  recommended_actions: string[]
  evidence_fragments: VideoEvidenceFragment[]
}

// State
const analysisResult = ref('')
const isLoading = ref(false)
const isStreaming = ref(false)
const error = ref<string | null>(null)
const contentRef = ref<HTMLElement | null>(null)
const videoRiskAssessment = ref<VideoRiskAssessment | null>(null)

// Markdown renderer
const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
})

// Computed rendered HTML
const renderedContent = computed(() => {
  if (!analysisResult.value) return ''
  return md.render(analysisResult.value)
})

// Auth store for token
const authStore = useAuthStore()

const riskTagType = (riskLevel: string) => {
  if (riskLevel === 'urgent' || riskLevel === 'high') return 'danger'
  if (riskLevel === 'medium') return 'warning'
  if (riskLevel === 'low') return 'success'
  return 'info'
}

const canOpenEvidence = (url?: string | null) => !!url && /^https?:\/\//i.test(url)

const openEvidence = (url?: string | null) => {
  if (!canOpenEvidence(url)) return
  window.open(url as string, '_blank', 'noopener,noreferrer')
}

// Scroll to bottom of content area
const scrollToBottom = () => {
  nextTick(() => {
    if (contentRef.value) {
      contentRef.value.scrollTop = contentRef.value.scrollHeight
    }
  })
}

// SSE Stream reading with fetch + ReadableStream
const startAnalysis = async () => {
  if (!props.deviceId) {
    error.value = '请先选择设备'
    return
  }

  // Reset state
  analysisResult.value = ''
  error.value = null
  isLoading.value = true
  isStreaming.value = false
  videoRiskAssessment.value = null

  const params = new URLSearchParams({
    device_id: props.deviceId,
    device_name: props.deviceName || props.deviceId,
  })

  // Only add pollutant if specified (single-factor mode)
  // If not specified, API will use comprehensive analysis
  if (props.pollutant) {
    params.set('pollutant', props.pollutant)
  }

  const url = `${apiBasePath}/ai/report/stream?${params}`

  try {
    const headers: Record<string, string> = {
      'Accept': 'text/event-stream'
    }

    // Add auth token if available
    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    const response = await fetch(url, { headers })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    if (!response.body) {
      throw new Error('Response body is null')
    }

    isLoading.value = false
    isStreaming.value = true

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // Parse SSE events
      while (buffer.includes('\n\n')) {
        const eventEnd = buffer.indexOf('\n\n')
        const eventStr = buffer.slice(0, eventEnd)
        buffer = buffer.slice(eventEnd + 2)

        let eventType = 'message'
        let eventData = ''

        for (const line of eventStr.split('\n')) {
          if (line.startsWith('event:')) {
            eventType = line.slice(6).trim()
          } else if (line.startsWith('data:')) {
            eventData = line.slice(5).trim()
          }
        }

        if (eventData) {
          try {
            const data = JSON.parse(eventData)

            switch (eventType) {
              case 'start':
              case 'progress':
                // Could show status message
                break
              case 'content':
                analysisResult.value += data.content || ''
                scrollToBottom()
                break
              case 'done':
                videoRiskAssessment.value = data.video_risk_assessment || null
                isStreaming.value = false
                break
              case 'error':
                error.value = data.error || '生成报告时发生错误'
                isStreaming.value = false
                break
            }
          } catch {
            // If not JSON, treat as raw content
            analysisResult.value += eventData
            scrollToBottom()
          }
        }
      }
    }

    isStreaming.value = false
  } catch (e) {
    isLoading.value = false
    isStreaming.value = false
    error.value = e instanceof Error ? e.message : '请求失败'
    console.error('AI Analysis error:', e)
  }
}

// Clear result
const clearResult = () => {
  analysisResult.value = ''
  error.value = null
  videoRiskAssessment.value = null
}

// Watch for device/pollutant changes to clear previous result
watch([() => props.deviceId, () => props.pollutant], () => {
  clearResult()
})
</script>

<template>
  <el-card class="ai-analysis-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <div class="header-left">
          <!-- AI Brain Icon SVG -->
          <svg class="ai-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" fill="url(#gradient1)" opacity="0.2"/>
            <path d="M12 4c-1.1 0-2 .9-2 2v1c0 .55.45 1 1 1h2c.55 0 1-.45 1-1V6c0-1.1-.9-2-2-2z" fill="url(#gradient1)"/>
            <path d="M8 9c-.55 0-1 .45-1 1v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1z" fill="url(#gradient1)"/>
            <path d="M16 9c-.55 0-1 .45-1 1v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1z" fill="url(#gradient1)"/>
            <path d="M12 14c-2.21 0-4 1.79-4 4h8c0-2.21-1.79-4-4-4z" fill="url(#gradient1)"/>
            <circle cx="9" cy="10" r="1.5" fill="url(#gradient2)"/>
            <circle cx="15" cy="10" r="1.5" fill="url(#gradient2)"/>
            <path d="M7 6.5C5.5 7 4.5 8 4 9.5M17 6.5c1.5.5 2.5 1.5 3 3M7 17.5C5.5 17 4.5 16 4 14.5M17 17.5c1.5-.5 2.5-1.5 3-3"
                  stroke="url(#gradient1)" stroke-width="1.5" stroke-linecap="round"/>
            <defs>
              <linearGradient id="gradient1" x1="2" y1="2" x2="22" y2="22">
                <stop offset="0%" stop-color="#667eea"/>
                <stop offset="100%" stop-color="#764ba2"/>
              </linearGradient>
              <linearGradient id="gradient2" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stop-color="#f093fb"/>
                <stop offset="100%" stop-color="#f5576c"/>
              </linearGradient>
            </defs>
          </svg>
          <span class="title">悦恩AI智能诊断</span>
          <!-- 显示当前选中的设备 -->
          <el-tag v-if="deviceName" type="info" size="small" class="device-tag">
            {{ deviceName }}
          </el-tag>
        </div>
        <div class="header-right">
          <el-button
            type="primary"
            size="small"
            :loading="isLoading"
            :disabled="isStreaming || !deviceId"
            @click="startAnalysis"
          >
            <template #icon>
              <svg v-if="!isLoading && !isStreaming" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M9.4 16.6L4.8 12l4.6-4.6L8 6l-6 6 6 6 1.4-1.4zm5.2 0L19.2 12l-4.6-4.6L16 6l6 6-6 6-1.4-1.4z"/>
              </svg>
            </template>
            {{ isStreaming ? '生成中...' : '开始诊断' }}
          </el-button>
          <el-button
            v-if="analysisResult"
            size="small"
            @click="clearResult"
          >
            清除
          </el-button>
        </div>
      </div>
    </template>

    <!-- Content Area -->
    <div class="content-wrapper">
      <!-- Loading State -->
      <div v-if="isLoading" class="loading-state">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span>正在连接 AI 服务...</span>
      </div>

      <!-- Error State -->
      <el-alert
        v-else-if="error"
        :title="error"
        type="error"
        show-icon
        closable
        @close="error = null"
      />

      <!-- Empty State -->
      <div v-else-if="!analysisResult && !isStreaming" class="empty-state">
        <svg class="empty-icon" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="50" cy="50" r="45" stroke="#e0e0e0" stroke-width="2" fill="none"/>
          <path d="M35 40c0-2.76 2.24-5 5-5s5 2.24 5 5-2.24 5-5 5-5-2.24-5-5z" fill="#c0c0c0"/>
          <path d="M55 40c0-2.76 2.24-5 5-5s5 2.24 5 5-2.24 5-5 5-5-2.24-5-5z" fill="#c0c0c0"/>
          <path d="M30 60c0 0 10 15 20 15s20-15 20-15" stroke="#c0c0c0" stroke-width="3" stroke-linecap="round"/>
        </svg>
        <p class="empty-text">
          <template v-if="deviceId">
            <!-- 已选择设备，引导点击诊断 -->
            点击"开始诊断"，AI 将<strong>综合分析该设备所有污染物数据</strong><br/>
            并生成智能运维报告
          </template>
          <template v-else>
            <!-- 未选择设备，引导去上方选择 -->
            请先在上方 <strong>【实时趋势 + AI预测】</strong> 模块选择设备<br/>
            然后点击"开始诊断"生成智能运维报告
          </template>
        </p>
        <div class="mode-tags">
          <el-tag type="success" size="small" class="mode-tag">
            单设备·全指标综合分析
          </el-tag>
        </div>
      </div>

      <!-- Result Content -->
      <div v-else ref="contentRef" class="result-content markdown-body">
        <div v-if="videoRiskAssessment" class="video-risk-summary">
          <div class="video-risk-header">
            <div>
              <div class="video-risk-title">视频联动风险摘要</div>
              <div class="video-risk-text">{{ videoRiskAssessment.summary }}</div>
            </div>
            <div class="video-risk-badges">
              <el-tag :type="riskTagType(videoRiskAssessment.overall_risk_level)" size="small" effect="dark">
                {{ videoRiskAssessment.overall_risk_label }}
              </el-tag>
              <span class="video-risk-score">{{ videoRiskAssessment.overall_risk_score }} 分</span>
            </div>
          </div>

          <div
            v-if="videoRiskAssessment.recommended_actions?.length"
            class="video-risk-actions"
          >
            <div class="video-risk-section-title">建议动作</div>
            <div
              v-for="action in videoRiskAssessment.recommended_actions.slice(0, 3)"
              :key="action"
              class="video-risk-action-item"
            >
              {{ action }}
            </div>
          </div>

          <div
            v-if="videoRiskAssessment.evidence_fragments?.length"
            class="video-risk-evidence-list"
          >
            <div class="video-risk-section-title">关键证据</div>
            <div
              v-for="item in videoRiskAssessment.evidence_fragments.slice(0, 2)"
              :key="item.event_id"
              class="video-risk-evidence-item"
            >
              <div class="video-risk-evidence-top">
                <div>
                  <div class="video-risk-evidence-title">{{ item.title }}</div>
                  <div class="video-risk-evidence-meta">
                    {{ item.occurred_at }} · {{ item.channel_name }} · {{ item.point_type_label }}
                  </div>
                </div>
                <el-tag :type="riskTagType(videoRiskAssessment.overall_risk_level)" size="small">
                  {{ item.risk_label }}
                </el-tag>
              </div>
              <div class="video-risk-evidence-data">{{ item.associated_data_summary }}</div>
              <div class="video-risk-evidence-action">{{ item.suggested_action }}</div>
              <div class="video-risk-evidence-links">
                <el-button
                  v-if="canOpenEvidence(item.snapshot_uri)"
                  link
                  type="primary"
                  @click="openEvidence(item.snapshot_uri)"
                >
                  查看截图
                </el-button>
                <el-button
                  v-if="canOpenEvidence(item.clip_uri)"
                  link
                  type="primary"
                  @click="openEvidence(item.clip_uri)"
                >
                  查看片段
                </el-button>
              </div>
            </div>
          </div>
        </div>
        <div v-html="renderedContent"></div>
        <span v-if="isStreaming" class="cursor-blink">|</span>
      </div>
    </div>
  </el-card>
</template>

<script lang="ts">
import { Loading } from '@element-plus/icons-vue'

export default {
  components: { Loading }
}
</script>

<style scoped>
.ai-analysis-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-icon {
  width: 28px;
  height: 28px;
}

.title {
  font-weight: 600;
  font-size: 15px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.header-right {
  display: flex;
  gap: 8px;
}

.content-wrapper {
  flex: 1;
  min-height: 300px;
  max-height: 500px;
  display: flex;
  flex-direction: column;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  gap: 12px;
}

.loading-icon {
  font-size: 32px;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  padding: 40px;
}

.empty-icon {
  width: 80px;
  height: 80px;
  margin-bottom: 16px;
  opacity: 0.6;
}

.empty-text {
  color: #909399;
  font-size: 14px;
  text-align: center;
  line-height: 1.8;
  margin: 0;
}

.empty-text strong {
  color: #67c23a;
}

.device-tag {
  margin-left: 8px;
  font-weight: normal;
}

.mode-tags {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  justify-content: center;
}

.mode-tag {
  /* margin handled by .mode-tags */
}

.result-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fafbfc;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.8;
}

.video-risk-summary {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid #d7e3f4;
  border-radius: 10px;
  background: linear-gradient(180deg, #ffffff 0%, #f4f8ff 100%);
}

.video-risk-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.video-risk-title {
  font-size: 14px;
  font-weight: 700;
  color: #24405f;
}

.video-risk-text {
  margin-top: 6px;
  color: #52637a;
  line-height: 1.6;
}

.video-risk-badges {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.video-risk-score {
  font-size: 13px;
  font-weight: 600;
  color: #24405f;
}

.video-risk-section-title {
  margin-top: 14px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 700;
  color: #35506f;
}

.video-risk-action-item {
  position: relative;
  padding-left: 12px;
  color: #43566f;
  line-height: 1.7;
}

.video-risk-action-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #5b8def;
}

.video-risk-evidence-list {
  display: grid;
  gap: 10px;
}

.video-risk-evidence-item {
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #e3ebf5;
}

.video-risk-evidence-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.video-risk-evidence-title {
  font-weight: 600;
  color: #24364d;
}

.video-risk-evidence-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #7b8aa0;
}

.video-risk-evidence-data,
.video-risk-evidence-action {
  margin-top: 8px;
  color: #4f6177;
  line-height: 1.6;
}

.video-risk-evidence-links {
  margin-top: 8px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* Markdown Styling */
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3) {
  margin-top: 1em;
  margin-bottom: 0.5em;
  font-weight: 600;
  color: #303133;
}

.markdown-body :deep(h1) {
  font-size: 1.4em;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 0.3em;
}

.markdown-body :deep(h2) {
  font-size: 1.2em;
  color: #409eff;
}

.markdown-body :deep(h3) {
  font-size: 1.1em;
  color: #606266;
}

.markdown-body :deep(p) {
  margin: 0.8em 0;
  color: #606266;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.markdown-body :deep(li) {
  margin: 0.3em 0;
  color: #606266;
}

.markdown-body :deep(strong) {
  color: #303133;
  font-weight: 600;
}

.markdown-body :deep(code) {
  background: #f0f2f5;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
  color: #e6a23c;
}

.markdown-body :deep(blockquote) {
  margin: 1em 0;
  padding: 0.5em 1em;
  border-left: 4px solid #409eff;
  background: #ecf5ff;
  color: #606266;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #ebeef5;
  padding: 8px 12px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f5f7fa;
  font-weight: 600;
}

/* Typing cursor animation */
.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #409eff;
  font-weight: bold;
}

@keyframes blink {
  50% { opacity: 0; }
}

/* Scrollbar styling */
.result-content::-webkit-scrollbar {
  width: 6px;
}

.result-content::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.result-content::-webkit-scrollbar-thumb {
  background: #c0c4cc;
  border-radius: 3px;
}

.result-content::-webkit-scrollbar-thumb:hover {
  background: #909399;
}
</style>
