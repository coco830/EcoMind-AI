<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
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

// Map container ref
const mapContainer = ref<HTMLDivElement | null>(null)

// Map instance and markers
let map: any = null
let markers: any[] = []
let infoWindow: any = null
let AMap: any = null

// Map initialization state
const mapReady = ref(false)
const mapError = ref<string | null>(null)

// Devices with valid coordinates
const validDevices = computed(() => {
  return props.devices.filter(
    d => d.latitude !== null && d.longitude !== null
  )
})

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
      return '在线'
    case 'alarm':
      return '告警'
    case 'offline':
      return '离线'
    case 'maintenance':
      return '维护中'
    default:
      return '未知'
  }
}

// Get device type text
const getDeviceTypeText = (type: string): string => {
  switch (type) {
    case 'water':
      return '水质监测'
    case 'air':
      return '空气监测'
    case 'noise':
      return '噪声监测'
    case 'soil':
      return '土壤监测'
    default:
      return type
  }
}

// Create custom marker content
const createMarkerContent = (color: string): string => {
  return `
    <div style="
      width: 28px;
      height: 38px;
      position: relative;
      cursor: pointer;
    ">
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="28" height="38">
        <path fill="${color}" stroke="#fff" stroke-width="1.5" d="M12 0C5.4 0 0 5.4 0 12c0 9 12 24 12 24s12-15 12-24c0-6.6-5.4-12-12-12z"/>
        <circle fill="#fff" cx="12" cy="12" r="5"/>
      </svg>
    </div>
  `
}

// Create info window content
const createInfoWindowContent = (device: Device): string => {
  const statusColor = getMarkerColor(device.status)
  const statusText = getStatusText(device.status)
  const typeText = getDeviceTypeText(device.device_type)

  return `
    <div style="min-width: 220px; padding: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #eee;">
        <span style="font-weight: 600; font-size: 15px; color: #333;">${device.name}</span>
        <span style="
          background: ${statusColor};
          color: #fff;
          padding: 2px 8px;
          border-radius: 10px;
          font-size: 11px;
          font-weight: 500;
        ">${statusText}</span>
      </div>
      <div style="display: flex; flex-direction: column; gap: 8px; font-size: 13px;">
        <div style="display: flex;">
          <span style="color: #909399; width: 60px; flex-shrink: 0;">MN号:</span>
          <span style="color: #333; word-break: break-all;">${device.mn}</span>
        </div>
        <div style="display: flex;">
          <span style="color: #909399; width: 60px; flex-shrink: 0;">类型:</span>
          <span style="color: #333;">${typeText}</span>
        </div>
        ${device.address ? `
        <div style="display: flex;">
          <span style="color: #909399; width: 60px; flex-shrink: 0;">地址:</span>
          <span style="color: #333; word-break: break-all;">${device.address}</span>
        </div>
        ` : ''}
        ${device.last_heartbeat ? `
        <div style="display: flex;">
          <span style="color: #909399; width: 60px; flex-shrink: 0;">最后活动:</span>
          <span style="color: #333;">${new Date(device.last_heartbeat).toLocaleString('zh-CN')}</span>
        </div>
        ` : ''}
      </div>
    </div>
  `
}

// Initialize AMap
const initMap = async () => {
  if (!mapContainer.value) return

  try {
    mapError.value = null

    // Get AMap config from environment variables
    const amapKey = import.meta.env.VITE_AMAP_KEY
    const amapSecurityCode = import.meta.env.VITE_AMAP_SECURITY_CODE

    if (!amapKey || !amapSecurityCode) {
      throw new Error('高德地图配置缺失，请检查环境变量')
    }

    // Set security config
    ;(window as any)._AMapSecurityConfig = {
      securityJsCode: amapSecurityCode
    }

    // Load AMap
    AMap = await AMapLoader.load({
      key: amapKey,
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.ToolBar']
    })

    // Default center (Wuhan)
    const defaultCenter = [114.4, 30.5]

    // Create map instance
    map = new AMap.Map(mapContainer.value, {
      zoom: 10,
      center: defaultCenter,
      viewMode: '2D',
      mapStyle: 'amap://styles/whitesmoke'
    })

    // Add controls
    map.addControl(new AMap.Scale())
    map.addControl(new AMap.ToolBar({
      position: 'RB'
    }))

    // Create info window
    infoWindow = new AMap.InfoWindow({
      isCustom: true,
      autoMove: true,
      offset: new AMap.Pixel(0, -40)
    })

    mapReady.value = true

    // Update markers if devices are already available
    await nextTick()
    updateMarkers()

  } catch (error) {
    console.error('Failed to load AMap:', error)
    mapError.value = '地图加载失败，请刷新重试'
  }
}

// Update markers on the map
const updateMarkers = () => {
  if (!map || !AMap || !mapReady.value) return

  // Clear existing markers
  markers.forEach(marker => {
    marker.setMap(null)
  })
  markers = []

  // Add new markers
  validDevices.value.forEach(device => {
    const color = getMarkerColor(device.status)

    // Create marker
    const marker = new AMap.Marker({
      position: new AMap.LngLat(device.longitude!, device.latitude!),
      content: createMarkerContent(color),
      offset: new AMap.Pixel(-14, -38),
      extData: device
    })

    // Add click event
    marker.on('click', () => {
      // Show info window
      infoWindow.setContent(createInfoWindowContent(device))
      infoWindow.open(map, marker.getPosition())

      // Emit device click event
      emit('device-click', device)
    })

    markers.push(marker)
    marker.setMap(map)
  })

  // Fit view to show all markers
  if (validDevices.value.length > 0) {
    setTimeout(() => {
      if (validDevices.value.length === 1) {
        map.setCenter([validDevices.value[0].longitude!, validDevices.value[0].latitude!])
        map.setZoom(14)
      } else if (markers.length > 1) {
        map.setFitView(markers, false, [50, 50, 50, 50])
      }
    }, 100)
  }
}

// Watch for device changes
watch(() => props.devices, () => {
  updateMarkers()
}, { deep: true })

// Lifecycle hooks
onMounted(() => {
  initMap()
})

onUnmounted(() => {
  // Clean up
  if (infoWindow) {
    infoWindow.close()
  }
  markers.forEach(marker => {
    marker.setMap(null)
  })
  markers = []
  if (map) {
    map.destroy()
    map = null
  }
})
</script>

<template>
  <div class="device-map" :style="{ height }">
    <!-- Loading overlay -->
    <div v-if="loading || !mapReady" class="map-loading">
      <el-icon class="is-loading" size="32"><Loading /></el-icon>
      <span>地图加载中...</span>
    </div>

    <!-- Error overlay -->
    <div v-if="mapError" class="map-error">
      <el-icon size="32" color="#f56c6c"><WarningFilled /></el-icon>
      <span>{{ mapError }}</span>
      <el-button type="primary" size="small" @click="initMap">重试</el-button>
    </div>

    <!-- Map container -->
    <div ref="mapContainer" class="map-container"></div>

    <!-- No data overlay -->
    <div v-if="validDevices.length === 0 && !loading && mapReady" class="no-data-overlay">
      <el-empty description="暂无带坐标的设备" :image-size="80" />
    </div>

    <!-- Legend -->
    <div class="map-legend">
      <div class="legend-item">
        <span class="legend-marker" style="background: #67c23a"></span>
        <span>在线</span>
      </div>
      <div class="legend-item">
        <span class="legend-marker" style="background: #f56c6c"></span>
        <span>告警</span>
      </div>
      <div class="legend-item">
        <span class="legend-marker" style="background: #909399"></span>
        <span>离线</span>
      </div>
      <div class="legend-item">
        <span class="legend-marker" style="background: #e6a23c"></span>
        <span>维护中</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { Loading, WarningFilled } from '@element-plus/icons-vue'
export default {
  components: { Loading, WarningFilled }
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

.map-error {
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

/* AMap info window custom styles */
:deep(.amap-info-content) {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  border: none;
  padding: 0;
}

:deep(.amap-info-sharp) {
  display: none;
}
</style>
