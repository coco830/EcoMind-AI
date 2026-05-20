<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, computed } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import type { RegulatorHeatmapCell } from '@/api/regulator'

const props = withDefaults(defineProps<{
  cells: RegulatorHeatmapCell[]
  height?: string
}>(), {
  height: '360px'
})

const cells = computed(() => props.cells || [])

const mapContainer = ref<HTMLDivElement | null>(null)
const mapReady = ref(false)
const mapError = ref<string | null>(null)

let map: any = null
let AMap: any = null
let polygons: any[] = []

const riskColors: Record<string, string> = {
  L1: '#3ABF7B',
  L2: '#8BCF5B',
  L3: '#F4C45C',
  L4: '#F29D4B',
  L5: '#E85B5B'
}

const riskLegend = [
  { level: 'L1', label: '低', range: '0-20' },
  { level: 'L2', label: '偏低', range: '20-40' },
  { level: 'L3', label: '中', range: '40-60' },
  { level: 'L4', label: '较高', range: '60-80' },
  { level: 'L5', label: '高', range: '80-100' }
]

const clearPolygons = () => {
  polygons.forEach(poly => poly.setMap(null))
  polygons = []
}

const updatePolygons = () => {
  if (!map || !AMap || !mapReady.value) return
  clearPolygons()
  if (cells.value.length === 0) return

  cells.value.forEach(cell => {
    const color = riskColors[cell.risk_level] || '#5B8FF9'
    const polygon = new AMap.Polygon({
      path: cell.boundary,
      strokeColor: color,
      strokeWeight: 1,
      fillColor: color,
      fillOpacity: 0.35
    })
    polygon.setMap(map)
    polygons.push(polygon)
  })

  if (polygons.length > 0) {
    map.setFitView(polygons, false, [40, 40, 40, 40])
  }
}

const initMap = async () => {
  if (!mapContainer.value) return

  const amapKey = import.meta.env.VITE_AMAP_KEY
  const amapSecurityCode = import.meta.env.VITE_AMAP_SECURITY_CODE
  if (!amapKey || !amapSecurityCode) {
    mapError.value = 'Missing AMap key or security code'
    return
  }

  try {
    ;(window as any)._AMapSecurityConfig = {
      securityJsCode: amapSecurityCode
    }

    AMap = await AMapLoader.load({
      key: amapKey,
      version: '2.0',
      plugins: ['AMap.Scale'],
      // AMapLoader typings omit securityJsCode; pass via cast to satisfy TS.
      securityJsCode: amapSecurityCode
    } as any)

    map = new AMap.Map(mapContainer.value, {
      zoom: 10,
      mapStyle: 'amap://styles/normal',
      viewMode: '2D'
    })

    map.addControl(new AMap.Scale())
    mapReady.value = true
    updatePolygons()
  } catch (err: any) {
    mapError.value = err?.message || 'Failed to load map'
  }
}

watch(
  () => props.cells,
  () => updatePolygons(),
  { deep: true }
)

onMounted(() => {
  initMap()
})

onBeforeUnmount(() => {
  clearPolygons()
  if (map) {
    map.destroy()
    map = null
  }
})
</script>

<template>
  <div class="regulator-heatmap" :style="{ height: props.height }">
    <div v-if="mapError" class="map-error">
      <span>{{ mapError }}</span>
    </div>
    <div v-else class="map-container" ref="mapContainer"></div>
    <div v-if="!mapError && mapReady && cells.length === 0" class="no-data">
      当前范围暂无数据
    </div>
    <div class="map-legend">
      <div class="legend-title">风险等级</div>
      <div class="legend-item" v-for="item in riskLegend" :key="item.level">
        <span class="legend-color" :style="{ backgroundColor: riskColors[item.level] }"></span>
        <span class="legend-label">{{ item.level }} {{ item.label }} ({{ item.range }})</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.regulator-heatmap {
  position: relative;
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  background: #f5f7fa;
}

.map-container {
  width: 100%;
  height: 100%;
}

.map-error,
.no-data {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.8);
  z-index: 2;
}

.map-legend {
  position: absolute;
  bottom: 12px;
  left: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  z-index: 3;
}

.legend-title {
  font-size: 12px;
  font-weight: 600;
  color: #1f2937;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #1f2937;
}

.legend-color {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}
</style>
