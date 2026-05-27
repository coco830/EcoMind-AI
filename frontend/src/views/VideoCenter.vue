<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus/es/components/message/index'
import { ElMessageBox } from 'element-plus/es/components/message-box/index'
import type { FormInstance, FormRules } from 'element-plus'

import { useAuthStore } from '@/stores/auth'
import { organizationApi, type Organization } from '@/api/organizations'
import { deviceApi, type Device } from '@/api/devices'
import {
  videoApi,
  type VideoAccessMethod,
  type VideoChannel,
  type VideoChannelCreate,
  type VideoDemoSeedResponse,
  type VideoLifecycleStatus,
  type VideoChannelStatus,
  type VideoEvent,
  type VideoEventCreate,
  type VideoEventLevel,
  type VideoEventSource,
  type VideoEventStatus,
  type VideoEventType,
  type VideoPointType,
  type VideoProtocol,
  type VideoSummary,
} from '@/api/video'

const route = useRoute()
const authStore = useAuthStore()

const loading = ref(false)
const summary = ref<VideoSummary>({
  total_channels: 0,
  pending_survey_channels: 0,
  pending_installation_channels: 0,
  pending_networking_channels: 0,
  commissioning_channels: 0,
  accepted_channels: 0,
  online_channels: 0,
  ai_enabled_channels: 0,
  fault_channels: 0,
  today_events: 0,
  pending_events: 0,
  linked_alarm_events: 0
})
const channels = ref<VideoChannel[]>([])
const events = ref<VideoEvent[]>([])
const devices = ref<Device[]>([])
const organizations = ref<Organization[]>([])

const filters = reactive({
  org_id: '',
  device_id: '',
  point_type: '',
  lifecycle_status: '',
  channel_status: '',
  event_status: '',
  level: '',
  related_alarm_id: ''
})

const canModify = computed(() => authStore.user?.is_superadmin === true)
const canFilterByOrg = computed(() => {
  return authStore.user?.is_superadmin === true || authStore.user?.role === 'doc_editor' || authStore.user?.role === 'viewer'
})

const pointTypeOptions: Array<{ value: VideoPointType; label: string }> = [
  { value: 'station_room', label: '监测站房' },
  { value: 'wastewater_outlet', label: '废水总排口' },
  { value: 'wastegas_outlet', label: '废气总排口' },
  { value: 'manual_sampling', label: '手工采样点' },
  { value: 'custom', label: '自定义点位' }
]

const protocolOptions: Array<{ value: VideoProtocol; label: string }> = [
  { value: 'gb28181', label: 'GB/T28181' },
  { value: 'rtsp', label: 'RTSP' },
  { value: 'onvif', label: 'ONVIF' },
  { value: 'http_link', label: 'HTTP链接' },
  { value: 'other', label: '其他' }
]

const accessMethodOptions: Array<{ value: VideoAccessMethod; label: string }> = [
  { value: 'operator_platform', label: '运营商平台' },
  { value: 'city_platform', label: '州市平台' },
  { value: 'direct', label: '直连接入' },
  { value: 'external_link', label: '外部跳转' }
]

const lifecycleStatusOptions: Array<{ value: VideoLifecycleStatus; label: string }> = [
  { value: 'pending_survey', label: '待勘点' },
  { value: 'pending_installation', label: '待安装' },
  { value: 'pending_networking', label: '待联网' },
  { value: 'commissioning', label: '联调中' },
  { value: 'accepted', label: '已验收' },
  { value: 'active', label: '已投运' }
]

const channelStatusOptions: Array<{ value: VideoChannelStatus; label: string }> = [
  { value: 'online', label: '在线' },
  { value: 'offline', label: '离线' },
  { value: 'fault', label: '故障' },
  { value: 'unknown', label: '未知' }
]

const eventTypeOptions: Array<{ value: VideoEventType; label: string }> = [
  { value: 'stream_offline', label: '视频离线' },
  { value: 'occlusion', label: '镜头遮挡' },
  { value: 'intrusion', label: '区域入侵' },
  { value: 'loitering', label: '徘徊滞留' },
  { value: 'wastewater_visual_anomaly', label: '废水可视异常' },
  { value: 'smoke_plume_change', label: '烟羽状态变化' },
  { value: 'manual_sampling', label: '采样作业' },
  { value: 'ai_linkage', label: 'AI联动' },
  { value: 'custom', label: '自定义事件' }
]

const eventStatusOptions: Array<{ value: VideoEventStatus; label: string }> = [
  { value: 'pending', label: '待处理' },
  { value: 'acknowledged', label: '已确认' },
  { value: 'resolved', label: '已解决' }
]

const eventLevelOptions: Array<{ value: VideoEventLevel; label: string }> = [
  { value: 'info', label: '提示' },
  { value: 'warning', label: '警告' },
  { value: 'critical', label: '严重' }
]

const eventSourceOptions: Array<{ value: VideoEventSource; label: string }> = [
  { value: 'manual', label: '手工登记' },
  { value: 'external_callback', label: '外部回调' },
  { value: 'ai_linkage', label: 'AI联动' },
  { value: 'inspection', label: '巡检发现' }
]

const loadOrganizations = async () => {
  if (!canFilterByOrg.value) return
  try {
    organizations.value = await organizationApi.list()
  } catch (error) {
    console.error('加载组织失败:', error)
  }
}

const loadDevices = async () => {
  try {
    const params: { org_id?: string } = {}
    if (filters.org_id) params.org_id = filters.org_id
    devices.value = await deviceApi.list(params)
  } catch (error) {
    console.error('加载设备失败:', error)
  }
}

const applyRouteFilters = () => {
  const queryDeviceId = typeof route.query.device_id === 'string' ? route.query.device_id : ''
  const queryAlarmId = typeof route.query.alarm_id === 'string' ? route.query.alarm_id : ''
  if (queryDeviceId) {
    filters.device_id = queryDeviceId
  }
  if (queryAlarmId) {
    filters.related_alarm_id = queryAlarmId
  }
}

const loadData = async () => {
  loading.value = true
  try {
    const summaryParams = filters.org_id ? { org_id: filters.org_id } : undefined
    const channelParams = {
      org_id: filters.org_id || undefined,
      device_id: filters.device_id || undefined,
      point_type: (filters.point_type || undefined) as VideoPointType | undefined,
      lifecycle_status: (filters.lifecycle_status || undefined) as VideoLifecycleStatus | undefined,
      status: (filters.channel_status || undefined) as VideoChannelStatus | undefined
    }
    const eventParams = {
      org_id: filters.org_id || undefined,
      device_id: filters.device_id || undefined,
      related_alarm_id: filters.related_alarm_id || undefined,
      status: (filters.event_status || undefined) as VideoEventStatus | undefined,
      level: (filters.level || undefined) as VideoEventLevel | undefined,
      limit: 100
    }

    const [summaryRes, channelsRes, eventsRes] = await Promise.all([
      videoApi.getSummary(summaryParams),
      videoApi.listChannels(channelParams),
      videoApi.listEvents(eventParams)
    ])

    summary.value = summaryRes
    channels.value = channelsRes
    events.value = eventsRes
  } catch {
    ElMessage.error('加载视频联动数据失败')
  } finally {
    loading.value = false
  }
}

const refreshAll = async () => {
  await loadDevices()
  await loadData()
}

watch(() => filters.org_id, async () => {
  if (filters.device_id && !canFilterByOrg.value) return
  filters.device_id = ''
  await refreshAll()
})

watch(
  () => [
    filters.device_id,
    filters.point_type,
    filters.lifecycle_status,
    filters.channel_status,
    filters.event_status,
    filters.level,
    filters.related_alarm_id
  ],
  () => {
    loadData()
  }
)

watch(
  () => [route.query.device_id, route.query.alarm_id],
  () => {
    applyRouteFilters()
    loadData()
  }
)

const getOrgName = (orgId: string) => {
  const org = organizations.value.find(item => item.id === orgId)
  return org?.name || orgId
}

const getPointTypeLabel = (value: string) => pointTypeOptions.find(item => item.value === value)?.label || value
const getProtocolLabel = (value: string) => protocolOptions.find(item => item.value === value)?.label || value
const getAccessMethodLabel = (value: string) => accessMethodOptions.find(item => item.value === value)?.label || value
const getLifecycleStatusLabel = (value: string) => lifecycleStatusOptions.find(item => item.value === value)?.label || value
const getChannelStatusLabel = (value: string) => channelStatusOptions.find(item => item.value === value)?.label || value
const getEventTypeLabel = (value: string) => eventTypeOptions.find(item => item.value === value)?.label || value
const getEventStatusLabel = (value: string) => eventStatusOptions.find(item => item.value === value)?.label || value
const getEventLevelLabel = (value: string) => eventLevelOptions.find(item => item.value === value)?.label || value

const getLifecycleStatusType = (value: string) => {
  const map: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
    pending_survey: 'info',
    pending_installation: 'warning',
    pending_networking: 'warning',
    commissioning: 'danger',
    accepted: 'success',
    active: 'success'
  }
  return map[value] || 'info'
}

const getChannelStatusType = (value: string) => {
  const map: Record<string, 'success' | 'info' | 'warning' | 'danger'> = {
    online: 'success',
    offline: 'info',
    fault: 'danger',
    unknown: 'warning'
  }
  return map[value] || 'info'
}

const getEventStatusType = (value: string) => {
  const map: Record<string, 'success' | 'info' | 'warning'> = {
    pending: 'warning',
    acknowledged: 'info',
    resolved: 'success'
  }
  return map[value] || 'info'
}

const getEventLevelType = (value: string) => {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
    info: 'info',
    warning: 'warning',
    critical: 'danger'
  }
  return map[value] || 'info'
}

const formatDateTimeValue = (value: string | null | undefined) => {
  if (!value) return ''
  return value.replace('Z', '').slice(0, 19)
}

const openExternal = (url: string | null) => {
  if (!url) return
  if (url.startsWith('mock://')) {
    ElMessage.info('当前为演示数据，无真实视频流；可先验证页面与联动流程。')
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

const injectDemoData = async () => {
  const fallbackOrgId = authStore.user?.org_id || ''

  if (!filters.org_id && !filters.device_id && !fallbackOrgId) {
    ElMessage.warning('请先选择企业或设备，再导入演示数据。')
    return
  }

  try {
    await ElMessageBox.confirm(
      '将为当前企业/设备生成一套演示视频台账、安装验收信息和联动事件。重复导入会替换旧的演示数据，是否继续？',
      '导入演示数据',
      { type: 'info' }
    )

    const result: VideoDemoSeedResponse = await videoApi.injectDemoData({
      org_id: filters.org_id || fallbackOrgId || undefined,
      device_id: filters.device_id || undefined,
      replace_existing: true,
      create_demo_devices_if_missing: true
    })

    ElMessage.success(
      `${result.message} 已生成 ${result.created_channels} 个通道、${result.created_events} 个事件、${result.created_alarms} 个告警。`
    )
    await refreshAll()
  } catch {
    // noop
  }
}

const channelDialogVisible = ref(false)
const channelDialogTitle = ref('新增视频通道')
const channelEditingId = ref<string | null>(null)
const channelFormRef = ref<FormInstance>()
const channelForm = reactive<VideoChannelCreate>({
  device_id: '',
  name: '',
  point_type: 'station_room',
  protocol: 'gb28181',
  access_method: 'operator_platform',
  lifecycle_status: 'pending_survey',
  status: 'unknown',
  vendor: '',
  channel_code: '',
  network_provider: '',
  fixed_ip: '',
  install_location: '',
  surveyor_name: '',
  installer_name: '',
  accepted_by: '',
  accepted_at: '',
  acceptance_notes: '',
  preview_url: '',
  playback_url: '',
  ai_enabled: false,
  notes: '',
  last_seen_at: ''
})

const channelRules: FormRules = {
  device_id: [{ required: true, message: '请选择绑定设备', trigger: 'change' }],
  name: [{ required: true, message: '请输入通道名称', trigger: 'blur' }]
}

const resetChannelForm = () => {
  channelEditingId.value = null
  channelDialogTitle.value = '新增视频通道'
  channelForm.device_id = filters.device_id || ''
  channelForm.name = ''
  channelForm.point_type = 'station_room'
  channelForm.protocol = 'gb28181'
  channelForm.access_method = 'operator_platform'
  channelForm.lifecycle_status = 'pending_survey'
  channelForm.status = 'unknown'
  channelForm.vendor = ''
  channelForm.channel_code = ''
  channelForm.network_provider = ''
  channelForm.fixed_ip = ''
  channelForm.install_location = ''
  channelForm.surveyor_name = ''
  channelForm.installer_name = ''
  channelForm.accepted_by = ''
  channelForm.accepted_at = ''
  channelForm.acceptance_notes = ''
  channelForm.preview_url = ''
  channelForm.playback_url = ''
  channelForm.ai_enabled = false
  channelForm.notes = ''
  channelForm.last_seen_at = ''
}

const openChannelDialog = (channel?: VideoChannel) => {
  resetChannelForm()
  if (channel) {
    channelDialogTitle.value = '编辑视频通道'
    channelEditingId.value = channel.id
    channelForm.device_id = channel.device_id
    channelForm.name = channel.name
    channelForm.point_type = channel.point_type
    channelForm.protocol = channel.protocol
    channelForm.access_method = channel.access_method
    channelForm.lifecycle_status = channel.lifecycle_status
    channelForm.status = channel.status
    channelForm.vendor = channel.vendor || ''
    channelForm.channel_code = channel.channel_code || ''
    channelForm.network_provider = channel.network_provider || ''
    channelForm.fixed_ip = channel.fixed_ip || ''
    channelForm.install_location = channel.install_location || ''
    channelForm.surveyor_name = channel.surveyor_name || ''
    channelForm.installer_name = channel.installer_name || ''
    channelForm.accepted_by = channel.accepted_by || ''
    channelForm.accepted_at = formatDateTimeValue(channel.accepted_at)
    channelForm.acceptance_notes = channel.acceptance_notes || ''
    channelForm.preview_url = channel.preview_url || ''
    channelForm.playback_url = channel.playback_url || ''
    channelForm.ai_enabled = channel.ai_enabled
    channelForm.notes = channel.notes || ''
    channelForm.last_seen_at = formatDateTimeValue(channel.last_seen_at)
  }
  channelDialogVisible.value = true
}

const submitChannel = async () => {
  const valid = await channelFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const payload: VideoChannelCreate = {
    device_id: channelForm.device_id,
    name: channelForm.name,
    point_type: channelForm.point_type,
    protocol: channelForm.protocol,
    access_method: channelForm.access_method,
    lifecycle_status: channelForm.lifecycle_status,
    status: channelForm.status,
    vendor: channelForm.vendor || undefined,
    channel_code: channelForm.channel_code || undefined,
    network_provider: channelForm.network_provider || undefined,
    fixed_ip: channelForm.fixed_ip || undefined,
    install_location: channelForm.install_location || undefined,
    surveyor_name: channelForm.surveyor_name || undefined,
    installer_name: channelForm.installer_name || undefined,
    accepted_by: channelForm.accepted_by || undefined,
    accepted_at: channelForm.accepted_at || undefined,
    acceptance_notes: channelForm.acceptance_notes || undefined,
    preview_url: channelForm.preview_url || undefined,
    playback_url: channelForm.playback_url || undefined,
    ai_enabled: channelForm.ai_enabled,
    notes: channelForm.notes || undefined,
    last_seen_at: channelForm.last_seen_at || undefined
  }

  try {
    if (channelEditingId.value) {
      await videoApi.updateChannel(channelEditingId.value, payload)
      ElMessage.success('视频通道更新成功')
    } else {
      await videoApi.createChannel(payload)
      ElMessage.success('视频通道创建成功')
    }
    channelDialogVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('保存视频通道失败')
  }
}

const deleteChannel = async (channel: VideoChannel) => {
  try {
    await ElMessageBox.confirm(`确定删除通道“${channel.name}”吗？`, '确认', { type: 'warning' })
    await videoApi.deleteChannel(channel.id)
    ElMessage.success('删除成功')
    await loadData()
  } catch {
    // noop
  }
}

const eventDialogVisible = ref(false)
const eventFormRef = ref<FormInstance>()
const eventForm = reactive<VideoEventCreate>({
  channel_id: '',
  related_alarm_id: '',
  event_type: 'custom',
  source: 'manual',
  level: 'warning',
  title: '',
  summary: '',
  snapshot_uri: '',
  clip_uri: '',
  occurred_at: ''
})

const eventRules: FormRules = {
  channel_id: [{ required: true, message: '请选择视频通道', trigger: 'change' }],
  title: [{ required: true, message: '请输入事件标题', trigger: 'blur' }]
}

const resetEventForm = () => {
  eventForm.channel_id = channels.value.find(item => item.device_id === filters.device_id)?.id || channels.value[0]?.id || ''
  eventForm.related_alarm_id = filters.related_alarm_id || ''
  eventForm.event_type = 'custom'
  eventForm.source = 'manual'
  eventForm.level = 'warning'
  eventForm.title = ''
  eventForm.summary = ''
  eventForm.snapshot_uri = ''
  eventForm.clip_uri = ''
  eventForm.occurred_at = ''
}

const openEventDialog = () => {
  resetEventForm()
  eventDialogVisible.value = true
}

const submitEvent = async () => {
  const valid = await eventFormRef.value?.validate().catch(() => false)
  if (!valid) return

  const payload: VideoEventCreate = {
    channel_id: eventForm.channel_id,
    related_alarm_id: eventForm.related_alarm_id || undefined,
    event_type: eventForm.event_type,
    source: eventForm.source,
    level: eventForm.level,
    title: eventForm.title,
    summary: eventForm.summary || undefined,
    snapshot_uri: eventForm.snapshot_uri || undefined,
    clip_uri: eventForm.clip_uri || undefined,
    occurred_at: eventForm.occurred_at || undefined
  }

  try {
    await videoApi.createEvent(payload)
    ElMessage.success('视频事件已登记')
    eventDialogVisible.value = false
    await loadData()
  } catch {
    ElMessage.error('保存视频事件失败')
  }
}

const acknowledgeEvent = async (event: VideoEvent) => {
  try {
    await videoApi.acknowledgeEvent(event.id)
    ElMessage.success('已确认')
    await loadData()
  } catch {
    ElMessage.error('确认失败')
  }
}

const resolveEvent = async (event: VideoEvent) => {
  try {
    await ElMessageBox.confirm(`确定将“${event.title}”标记为已解决吗？`, '确认', { type: 'info' })
    await videoApi.resolveEvent(event.id)
    ElMessage.success('已解决')
    await loadData()
  } catch {
    // noop
  }
}

const visibleAlarmHint = computed(() => !!filters.related_alarm_id)

onMounted(async () => {
  await loadOrganizations()
  await loadDevices()
  applyRouteFilters()
  await loadData()
})
</script>

<template>
  <div class="video-center-page" v-loading="loading">
    <el-alert
      title="当前视频中心已支持视频接入台账、安装验收管理和告警联动事件；在企业侧 VMS 尚未就绪时，可先沉淀点位、网络、实施与验收信息。"
      type="success"
      show-icon
      :closable="false"
    />
    <el-alert
      v-if="visibleAlarmHint"
      title="当前已按告警过滤视频事件，可直接补登记与该告警关联的视频证据。"
      type="info"
      show-icon
      :closable="false"
      class="alarm-hint"
    />

    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-value">{{ summary.total_channels }}</div>
        <div class="summary-label">视频通道总数</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{{ summary.pending_survey_channels }}</div>
        <div class="summary-label">待现场勘点</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{{ summary.pending_installation_channels }}</div>
        <div class="summary-label">待安装</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{{ summary.pending_networking_channels }}</div>
        <div class="summary-label">待联网</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{{ summary.commissioning_channels }}</div>
        <div class="summary-label">联调中</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{{ summary.accepted_channels }}</div>
        <div class="summary-label">已验收/投运</div>
      </div>
      <div class="summary-card danger">
        <div class="summary-value">{{ summary.pending_events }}</div>
        <div class="summary-label">待处理视频事件</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{{ summary.linked_alarm_events }}</div>
        <div class="summary-label">已关联告警事件</div>
      </div>
    </div>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>筛选条件</span>
          <div class="header-actions">
            <el-button v-if="canModify" type="primary" plain @click="injectDemoData">导入演示数据</el-button>
            <el-button @click="refreshAll">刷新</el-button>
          </div>
        </div>
      </template>
      <div class="filter-bar">
        <el-select
          v-if="canFilterByOrg"
          v-model="filters.org_id"
          placeholder="筛选企业"
          clearable
          filterable
          style="width: 220px"
        >
          <el-option
            v-for="org in organizations"
            :key="org.id"
            :label="org.name"
            :value="org.id"
          />
        </el-select>
        <el-select v-model="filters.device_id" placeholder="筛选设备" clearable filterable style="width: 220px">
          <el-option
            v-for="device in devices"
            :key="device.id"
            :label="device.name"
            :value="device.id"
          />
        </el-select>
        <el-select v-model="filters.point_type" placeholder="点位类型" clearable style="width: 180px">
          <el-option
            v-for="option in pointTypeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="filters.lifecycle_status" placeholder="建设阶段" clearable style="width: 180px">
          <el-option
            v-for="option in lifecycleStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="filters.channel_status" placeholder="通道状态" clearable style="width: 160px">
          <el-option
            v-for="option in channelStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="filters.event_status" placeholder="事件状态" clearable style="width: 160px">
          <el-option
            v-for="option in eventStatusOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-select v-model="filters.level" placeholder="事件级别" clearable style="width: 160px">
          <el-option
            v-for="option in eventLevelOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
      </div>
      <div class="filter-note">
        <span v-if="filters.related_alarm_id">关联告警：{{ filters.related_alarm_id }}</span>
        <span v-else>支持按企业、设备、点位和建设阶段查看接入进度，尚未接入真实视频流时也可先维护交付台账。</span>
      </div>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>视频通道</span>
          <el-button v-if="canModify" type="primary" @click="openChannelDialog()">新增通道</el-button>
        </div>
      </template>

      <el-table :data="channels" stripe>
        <el-table-column v-if="canFilterByOrg" label="所属企业" width="160">
          <template #default="{ row }">
            {{ getOrgName(row.org_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="device_name" label="关联设备" min-width="160" show-overflow-tooltip />
        <el-table-column prop="name" label="通道名称" min-width="160" show-overflow-tooltip />
        <el-table-column label="点位类型" width="140">
          <template #default="{ row }">
            {{ getPointTypeLabel(row.point_type) }}
          </template>
        </el-table-column>
        <el-table-column label="建设阶段" width="120">
          <template #default="{ row }">
            <el-tag :type="getLifecycleStatusType(row.lifecycle_status)" size="small">
              {{ getLifecycleStatusLabel(row.lifecycle_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="接入方式" width="140">
          <template #default="{ row }">
            {{ getAccessMethodLabel(row.access_method) }}
          </template>
        </el-table-column>
        <el-table-column label="协议" width="120">
          <template #default="{ row }">
            {{ getProtocolLabel(row.protocol) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getChannelStatusType(row.status)" size="small">
              {{ getChannelStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="网络 / 固定IP" min-width="180">
          <template #default="{ row }">
            <div>{{ row.network_provider || '-' }}</div>
            <div class="subtle-line">{{ row.fixed_ip || '-' }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="install_location" label="安装位置" min-width="180" show-overflow-tooltip />
        <el-table-column label="AI" width="90">
          <template #default="{ row }">
            <el-tag :type="row.ai_enabled ? 'success' : 'info'" size="small">
              {{ row.ai_enabled ? '已启用' : '未启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="channel_code" label="通道编码" width="150" show-overflow-tooltip />
        <el-table-column label="验收信息" min-width="180">
          <template #default="{ row }">
            <div>{{ row.accepted_by || '-' }}</div>
            <div class="subtle-line">
              {{ row.accepted_at ? new Date(row.accepted_at).toLocaleString() : '未验收' }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="last_seen_at" label="最近上报" width="180">
          <template #default="{ row }">
            {{ row.last_seen_at ? new Date(row.last_seen_at).toLocaleString() : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="链接" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="openExternal(row.preview_url)">预览</el-button>
            <el-button link type="primary" @click="openExternal(row.playback_url)">回放</el-button>
          </template>
        </el-table-column>
        <el-table-column v-if="canModify" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openChannelDialog(row)">编辑</el-button>
            <el-button link type="danger" @click="deleteChannel(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>视频事件</span>
          <el-button v-if="canModify" type="primary" @click="openEventDialog">登记事件</el-button>
        </div>
      </template>

      <el-table :data="events" stripe>
        <el-table-column prop="occurred_at" label="发生时间" width="180">
          <template #default="{ row }">
            {{ new Date(row.occurred_at).toLocaleString() }}
          </template>
        </el-table-column>
        <el-table-column label="级别" width="90">
          <template #default="{ row }">
            <el-tag :type="getEventLevelType(row.level)" size="small">
              {{ getEventLevelLabel(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="事件类型" width="140">
          <template #default="{ row }">
            {{ getEventTypeLabel(row.event_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="channel_name" label="通道" min-width="140" />
        <el-table-column prop="device_name" label="设备" min-width="140" />
        <el-table-column prop="title" label="事件标题" min-width="200" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getEventStatusType(row.status)" size="small">
              {{ getEventStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="related_alarm_id" label="关联告警" width="170">
          <template #default="{ row }">
            {{ row.related_alarm_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="证据" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="openExternal(row.snapshot_uri)">截图</el-button>
            <el-button link type="primary" @click="openExternal(row.clip_uri)">片段</el-button>
          </template>
        </el-table-column>
        <el-table-column v-if="canModify" label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              link
              type="primary"
              @click="acknowledgeEvent(row)"
            >
              确认
            </el-button>
            <el-button
              v-if="row.status !== 'resolved'"
              link
              type="success"
              @click="resolveEvent(row)"
            >
              解决
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="channelDialogVisible" :title="channelDialogTitle" width="720px">
      <el-form ref="channelFormRef" :model="channelForm" :rules="channelRules" label-width="110px">
        <el-form-item label="绑定设备" prop="device_id">
          <el-select v-model="channelForm.device_id" filterable style="width: 100%">
            <el-option
              v-for="device in devices"
              :key="device.id"
              :label="`${device.name} (${device.mn})`"
              :value="device.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="通道名称" prop="name">
          <el-input v-model="channelForm.name" placeholder="例如：废水总排口1" />
        </el-form-item>
        <el-form-item label="点位类型">
          <el-select v-model="channelForm.point_type" style="width: 100%">
            <el-option v-for="option in pointTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="接入方式">
          <el-select v-model="channelForm.access_method" style="width: 100%">
            <el-option v-for="option in accessMethodOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="建设阶段">
          <el-select v-model="channelForm.lifecycle_status" style="width: 100%">
            <el-option v-for="option in lifecycleStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="协议类型">
          <el-select v-model="channelForm.protocol" style="width: 100%">
            <el-option v-for="option in protocolOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="通道状态">
          <el-select v-model="channelForm.status" style="width: 100%">
            <el-option v-for="option in channelStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="厂商">
          <el-input v-model="channelForm.vendor" placeholder="海康 / 大华 / 电信平台等" />
        </el-form-item>
        <el-form-item label="通道编码">
          <el-input v-model="channelForm.channel_code" placeholder="设备编码/通道编号" />
        </el-form-item>
        <el-form-item label="网络承载">
          <el-input v-model="channelForm.network_provider" placeholder="电信 / 联通 / 移动 / 企业专网" />
        </el-form-item>
        <el-form-item label="固定IP">
          <el-input v-model="channelForm.fixed_ip" placeholder="如有固定IP可登记" />
        </el-form-item>
        <el-form-item label="安装位置">
          <el-input v-model="channelForm.install_location" placeholder="例如：废水总排口东北侧立杆，朝向采样槽" />
        </el-form-item>
        <el-form-item label="勘点负责人">
          <el-input v-model="channelForm.surveyor_name" placeholder="现场勘点人员或环保管家负责人" />
        </el-form-item>
        <el-form-item label="实施安装人">
          <el-input v-model="channelForm.installer_name" placeholder="施工/安装负责人" />
        </el-form-item>
        <el-form-item label="验收人">
          <el-input v-model="channelForm.accepted_by" placeholder="项目或业主侧验收人" />
        </el-form-item>
        <el-form-item label="验收时间">
          <el-date-picker
            v-model="channelForm.accepted_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="可选"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="验收说明">
          <el-input
            v-model="channelForm.acceptance_notes"
            type="textarea"
            :rows="3"
            placeholder="记录机位效果、联网情况、取证范围和整改项"
          />
        </el-form-item>
        <el-form-item label="预览链接">
          <el-input v-model="channelForm.preview_url" placeholder="可填写平台预览地址" />
        </el-form-item>
        <el-form-item label="回放链接">
          <el-input v-model="channelForm.playback_url" placeholder="可填写平台回放地址" />
        </el-form-item>
        <el-form-item label="最近上报">
          <el-date-picker
            v-model="channelForm.last_seen_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="可选"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="启用AI">
          <el-switch v-model="channelForm.ai_enabled" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="channelForm.notes" type="textarea" :rows="3" placeholder="可记录安装位置、排口编号、运维说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="channelDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitChannel">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="eventDialogVisible" title="登记视频事件" width="720px">
      <el-form ref="eventFormRef" :model="eventForm" :rules="eventRules" label-width="110px">
        <el-form-item label="视频通道" prop="channel_id">
          <el-select v-model="eventForm.channel_id" filterable style="width: 100%">
            <el-option
              v-for="channel in channels"
              :key="channel.id"
              :label="`${channel.name} / ${channel.device_name || channel.device_mn}`"
              :value="channel.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="关联告警">
          <el-input v-model="eventForm.related_alarm_id" placeholder="可选，填写告警ID" />
        </el-form-item>
        <el-form-item label="事件类型">
          <el-select v-model="eventForm.event_type" style="width: 100%">
            <el-option v-for="option in eventTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="事件来源">
          <el-select v-model="eventForm.source" style="width: 100%">
            <el-option v-for="option in eventSourceOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="事件级别">
          <el-select v-model="eventForm.level" style="width: 100%">
            <el-option v-for="option in eventLevelOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="事件标题" prop="title">
          <el-input v-model="eventForm.title" placeholder="例如：COD超标时废水颜色明显变深" />
        </el-form-item>
        <el-form-item label="事件说明">
          <el-input v-model="eventForm.summary" type="textarea" :rows="3" placeholder="记录现场异常现象、初判结果或处置建议" />
        </el-form-item>
        <el-form-item label="截图地址">
          <el-input v-model="eventForm.snapshot_uri" placeholder="可填 COS URI 或 HTTPS 地址" />
        </el-form-item>
        <el-form-item label="片段地址">
          <el-input v-model="eventForm.clip_uri" placeholder="可填 COS URI 或 HTTPS 地址" />
        </el-form-item>
        <el-form-item label="发生时间">
          <el-date-picker
            v-model="eventForm.occurred_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="默认使用当前时间"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="eventDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEvent">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.video-center-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.alarm-hint {
  border-radius: 12px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.summary-card {
  background: linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: 16px;
  padding: 18px 20px;
}

.summary-card.danger {
  background: linear-gradient(135deg, #fff5f5 0%, #ffe3e3 100%);
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: #0f172a;
}

.summary-label {
  margin-top: 6px;
  font-size: 13px;
  color: #475569;
}

.subtle-line {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.filter-note {
  margin-top: 12px;
  color: #64748b;
  font-size: 13px;
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
