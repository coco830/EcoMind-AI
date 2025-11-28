import { request } from './request'

export interface PredictionPoint {
  timestamp: string
  value: number          // yhat - predicted value
  confidence: number
  value_lower: number    // yhat_lower - lower bound of confidence interval
  value_upper: number    // yhat_upper - upper bound of confidence interval
}

export interface HistoricalPoint {
  timestamp: string
  value: number
}

export interface PredictionResponse {
  device_id: string
  pollutant_code: string
  time_range: {
    start: string
    end: string
  }
  historical_data: HistoricalPoint[]
  predictions: PredictionPoint[]
  model_type: string
  metrics: Record<string, number>
  message?: string
}

export interface PredictParams {
  pollutant_code?: string
  hours?: number
  prediction_hours?: number
}

export const aiApi = {
  /**
   * Get trend prediction for a device
   */
  predict(deviceId: string, params?: PredictParams): Promise<PredictionResponse> {
    return request.get(`/ai/predict/${deviceId}`, { params })
  }
}
