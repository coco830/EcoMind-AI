/**
 * 设备状态管理
 * 支持活跃因子管理和动态污染物配置
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { deviceApi, type Device } from '@/api/devices'
import { COMMON_POLLUTANTS, AIR_COMMON_POLLUTANTS, POLLUTANT_MAP, getPollutantInfo } from '@/config/pollutants'

export interface ActivePollutant {
  code: string
  name: string
  unit: string
  latestValue?: number
  flag?: string
  timestamp?: string
}

export interface DeviceWithPollutants extends Device {
  activePollutants?: ActivePollutant[]
}

export const useDeviceStore = defineStore('device', () => {
  // 设备列表
  const devices = ref<DeviceWithPollutants[]>([])
  // 当前选中设备
  const selectedDevice = ref<DeviceWithPollutants | null>(null)
  // 当前选中设备的活跃污染物
  const activePollutants = ref<string[]>([])
  // 加载状态
  const loading = ref(false)
  // 错误信息
  const error = ref<string | null>(null)

  // 计算属性：获取活跃污染物的详细信息
  const activePollutantDetails = computed((): ActivePollutant[] => {
    return activePollutants.value.map(code => {
      const info = getPollutantInfo(code)
      return {
        code,
        name: info?.name || code,
        unit: info?.unit || 'mg/L'
      }
    })
  })

  // 从设备的 pollutant_codes 字段解析活跃污染物
  function parseDevicePollutants(device: Device): string[] {
    const codes = device.pollutant_codes
    if (!codes) {
      return device.device_type === 'air' ? AIR_COMMON_POLLUTANTS : COMMON_POLLUTANTS
    }

    // 支持多种格式：数组、逗号分隔字符串、JSON字符串
    if (Array.isArray(codes)) {
      return codes
    }

    // 处理可能的字符串类型（兼容旧数据）
    const codesStr = codes as unknown as string
    if (typeof codesStr === 'string') {
      try {
        // 尝试解析 JSON
        const parsed = JSON.parse(codesStr)
        if (Array.isArray(parsed)) return parsed
      } catch {
        // 逗号分隔
        return codesStr.split(',').map((s: string) => s.trim()).filter(Boolean)
      }
    }

    return device.device_type === 'air' ? AIR_COMMON_POLLUTANTS : COMMON_POLLUTANTS
  }

  // 加载设备列表
  async function loadDevices() {
    loading.value = true
    error.value = null
    try {
      const list = await deviceApi.list()
      devices.value = list.map(device => ({
        ...device,
        activePollutants: parseDevicePollutants(device).map(code => {
          const info = getPollutantInfo(code)
          return {
            code,
            name: info?.name || code,
            unit: info?.unit || 'mg/L'
          }
        })
      }))

      // 如果有设备且未选中，自动选中第一个
      if (devices.value.length > 0 && !selectedDevice.value) {
        selectDevice(devices.value[0])
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '加载设备列表失败'
      console.error('Failed to load devices:', e)
    } finally {
      loading.value = false
    }
  }

  // 选中设备
  function selectDevice(device: DeviceWithPollutants | null) {
    selectedDevice.value = device
    if (device) {
      activePollutants.value = parseDevicePollutants(device)
    } else {
      activePollutants.value = []
    }
  }

  // 通过 MN 选中设备
  function selectDeviceByMn(mn: string) {
    const device = devices.value.find(d => d.mn === mn)
    if (device) {
      selectDevice(device)
    }
  }

  // 更新设备的活跃污染物
  async function updateDevicePollutants(deviceId: string, pollutantCodes: string[]) {
    try {
      // TODO: 调用后端API更新设备配置
      // await deviceApi.update(deviceId, { pollutant_codes: pollutantCodes })

      // 更新本地状态
      const device = devices.value.find(d => d.id === deviceId)
      if (device) {
        device.pollutant_codes = pollutantCodes
        device.activePollutants = pollutantCodes.map(code => {
          const info = getPollutantInfo(code)
          return {
            code,
            name: info?.name || code,
            unit: info?.unit || 'mg/L'
          }
        })
      }

      if (selectedDevice.value?.id === deviceId) {
        activePollutants.value = pollutantCodes
      }
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : '更新设备配置失败'
      throw e
    }
  }

  // 根据监测数据动态更新活跃污染物
  function updateActivePollutantsFromData(pollutantCodes: string[]) {
    // 过滤出已知的污染物编码
    const knownCodes = pollutantCodes.filter(code => POLLUTANT_MAP[code.toLowerCase()])
    if (knownCodes.length > 0) {
      activePollutants.value = [...new Set([...activePollutants.value, ...knownCodes])]
    }
  }

  // 获取设备名称
  function getDeviceName(mn: string): string {
    const device = devices.value.find(d => d.mn === mn)
    return device?.name || mn
  }

  // 重置状态
  function reset() {
    devices.value = []
    selectedDevice.value = null
    activePollutants.value = []
    loading.value = false
    error.value = null
  }

  return {
    // 状态
    devices,
    selectedDevice,
    activePollutants,
    activePollutantDetails,
    loading,
    error,
    // 方法
    loadDevices,
    selectDevice,
    selectDeviceByMn,
    updateDevicePollutants,
    updateActivePollutantsFromData,
    getDeviceName,
    reset,
    parseDevicePollutants,
  }
})
