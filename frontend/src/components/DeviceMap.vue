<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { LMap, LTileLayer, LMarker, LPopup, LIcon } from '@vue-leaflet/vue-leaflet'
import 'leaflet/dist/leaflet.css'
import type { Device } from '@/api/devices'

interface Props {
  devices: Device[]
  height?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  height: '400px',
  loading: false
})

const emit = defineEmits<{
  (e: 'device-click', device: Device): void
}>()

// Map ref and state
const mapRef = ref<InstanceType<typeof LMap> | null>(null)
const center = ref<[number, number]>([30.5, 114.4]) // Default to Wuhan
const zoom = ref(10)

// Devices with valid coordinates
const validDevices = computed(() => {
  return props.devices.filter(
    d => d.latitude !== null && d.longitude !== null
  )
})

// Calculate map bounds based on devices
const updateMapCenter = () => {
  if (validDevices.value.length === 0) return

  const lats = validDevices.value.map(d => d.latitude!)
  const lngs = validDevices.value.map(d => d.longitude!)

  const avgLat = lats.reduce((a, b) => a + b, 0) / lats.length
  const avgLng = lngs.reduce((a, b) => a + b, 0) / lngs.length

  center.value = [avgLat, avgLng]

  // Adjust zoom based on spread
  const latSpread = Math.max(...lats) - Math.min(...lats)
  const lngSpread = Math.max(...lngs) - Math.min(...lngs)
  const spread = Math.max(latSpread, lngSpread)

  if (spread > 5) zoom.value = 6
  else if (spread > 2) zoom.value = 8
  else if (spread > 0.5) zoom.value = 10
  else zoom.value = 12
}

// Get marker color based on device status
const getMarkerColor = (status: string): string => {
  switch (status) {
    case 'online':
      return '#67c23a' // Green
    case 'alarm':
      return '#f56c6c' // Red
    case 'offline':
      return '#909399' // Gray
    case 'maintenance':
      return '#e6a23c' // Orange
    default:
      return '#909399'
  }
}

// Get status text
const getStatusText = (status: string): string => {
  switch (status) {
    case 'online':
      return 'online'
    case 'alarm':
      return 'alarm'
    case 'offline':
      return 'offline'
    case 'maintenance':
      return 'maintenance'
    default:
      return 'unknown'
  }
}

// Get device type text
const getDeviceTypeText = (type: string): string => {
  switch (type) {
    case 'water':
      return 'water'
    case 'air':
      return 'air'
    case 'noise':
      return 'noise'
    case 'soil':
      return 'soil'
    default:
      return type
  }
}

// Create custom icon SVG
const createMarkerIcon = (color: string) => {
  return `data:image/svg+xml,${encodeURIComponent(`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="24" height="36">
      <path fill="${color}" stroke="#fff" stroke-width="1" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24c0-6.6-5.4-12-12-12z"/>
      <circle fill="#fff" cx="12" cy="12" r="5"/>
    </svg>
  `)}`
}

const handleMarkerClick = (device: Device) => {
  emit('device-click', device)
}

watch(() => props.devices, updateMapCenter, { immediate: true })

onMounted(() => {
  updateMapCenter()
})
</script>

<template>
  <div class="device-map" :style="{ height }">
    <!-- Loading overlay - 使用 v-show 保持地图容器始终存在 -->
    <div v-show="loading" class="map-loading">
      <el-icon class="is-loading" size="32"><Loading /></el-icon>
      <span>Loading...</span>
    </div>
    <l-map
      v-show="!loading"
      ref="mapRef"
      :zoom="zoom"
      :center="center"
      :use-global-leaflet="false"
      class="map-container"
    >
      <l-tile-layer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        layer-type="base"
        name="OpenStreetMap"
      />
      <l-marker
        v-for="device in validDevices"
        :key="device.id"
        :lat-lng="[device.latitude!, device.longitude!]"
        @click="handleMarkerClick(device)"
      >
        <l-icon
          :icon-url="createMarkerIcon(getMarkerColor(device.status))"
          :icon-size="[24, 36]"
          :icon-anchor="[12, 36]"
          :popup-anchor="[0, -36]"
        />
        <l-popup>
          <div class="popup-content">
            <div class="popup-header">
              <span class="device-name">{{ device.name }}</span>
              <el-tag
                :type="device.status === 'online' ? 'success' : device.status === 'alarm' ? 'danger' : 'info'"
                size="small"
              >
                {{ getStatusText(device.status) }}
              </el-tag>
            </div>
            <div class="popup-info">
              <div class="info-row">
                <span class="label">MN:</span>
                <span class="value">{{ device.mn }}</span>
              </div>
              <div class="info-row">
                <span class="label">Type:</span>
                <span class="value">{{ getDeviceTypeText(device.device_type) }}</span>
              </div>
              <div class="info-row" v-if="device.address">
                <span class="label">Address:</span>
                <span class="value">{{ device.address }}</span>
              </div>
              <div class="info-row" v-if="device.last_heartbeat">
                <span class="label">Last seen:</span>
                <span class="value">{{ new Date(device.last_heartbeat).toLocaleString('zh-CN') }}</span>
              </div>
            </div>
          </div>
        </l-popup>
      </l-marker>
    </l-map>
    <div v-if="validDevices.length === 0 && !loading" class="no-data-overlay">
      <el-empty description="No devices with location data" :image-size="80" />
    </div>
    <!-- Legend -->
    <div class="map-legend">
      <div class="legend-item">
        <span class="legend-marker" style="background: #67c23a"></span>
        <span>Online</span>
      </div>
      <div class="legend-item">
        <span class="legend-marker" style="background: #f56c6c"></span>
        <span>Alarm</span>
      </div>
      <div class="legend-item">
        <span class="legend-marker" style="background: #909399"></span>
        <span>Offline</span>
      </div>
      <div class="legend-item">
        <span class="legend-marker" style="background: #e6a23c"></span>
        <span>Maintenance</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Loading } from '@element-plus/icons-vue'
export default {
  components: { Loading }
}
</script>

<style scoped>
.device-map {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: #f5f7fa;
}

.map-container {
  width: 100%;
  height: 100%;
  z-index: 1;
}

.map-loading {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
  gap: 12px;
  color: #909399;
  z-index: 10;
}

.no-data-overlay {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  padding: 20px;
  border-radius: 8px;
}

.map-legend {
  position: absolute;
  bottom: 10px;
  right: 10px;
  background: rgba(255, 255, 255, 0.95);
  padding: 8px 12px;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-marker {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.popup-content {
  min-width: 200px;
}

.popup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #eee;
}

.device-name {
  font-weight: bold;
  font-size: 14px;
  color: #333;
}

.popup-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.info-row {
  display: flex;
  font-size: 12px;
}

.info-row .label {
  color: #909399;
  width: 70px;
  flex-shrink: 0;
}

.info-row .value {
  color: #333;
  word-break: break-all;
}
</style>
