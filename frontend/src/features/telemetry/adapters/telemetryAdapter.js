/**
 * Normalizes telemetry metrics into standard units and formatted strings
 * @param {any} raw
 * @param {boolean} [isMockMode=false]
 * @returns {any}
 */
const MOCK_SOURCES = {
  temperature: 'SIMULATED',
  humidity: 'SIMULATED',
  co2: 'SIMULATED',
  lux: 'SIMULATED',
  audio: 'SIMULATED',
  networkRssi: 'SIMULATED',
}

export function normalizeTelemetry(raw, isMockMode = false) {
  if (!raw) {
    return null
  }

  const metrics = raw.metrics || raw

  const temp = metrics.temperature ?? metrics.temp
  const hum = metrics.humidity ?? metrics.hum
  const co2 = metrics.co2 ?? metrics.co2_ppm
  const light = metrics.light ?? metrics.lux

  // INT01-R1: only a server-provided timestamp; never fabricate "now" for missing data
  const rawTime =
    raw.receivedAt ||
    raw.received_at ||
    raw.timestamp ||
    raw.recorded_at ||
    null

  return {
    deviceId: raw.deviceId || raw.device_id || null,
    farmId: raw.farmId || raw.farm_id || null,
    mode: raw.state?.mode || raw.mode || null,
    actuators: raw.actuators || null,
    temperature: temp != null ? Number(temp) : isMockMode ? 28.5 : null,
    humidity: hum != null ? Number(hum) : isMockMode ? 78 : null,
    co2: co2 != null ? Number(co2) : isMockMode ? 620 : null,
    light: light != null ? Number(light) : isMockMode ? 120 : null,
    timestamp: rawTime,
    // INT01-R1 provenance (IoT metricSources / provenance); mock mode is explicitly simulated
    sources: raw.metricSources || (isMockMode ? MOCK_SOURCES : null),
    provenanceSource: raw.provenance?.source || (isMockMode ? 'SIMULATED' : null),
    networkRssi: raw.state?.networkRssi ?? null,
    status:
      metrics.status ||
      (temp != null ? (Number(temp) > 31 ? 'Cảnh báo' : 'Ổn định') : isMockMode ? 'Ổn định' : 'Chưa có dữ liệu'),
  }
}

export const DEFAULT_HEADER_ENVIRONMENT = [
  { id: 'temperature', label: 'Nhiệt độ', value: '28.5°C' },
  { id: 'humidity', label: 'Độ ẩm', value: '78%' },
  { id: 'co2', label: 'CO₂', value: '620 ppm' },
  { id: 'light', label: 'Ánh sáng', value: '120 lux' },
]

export const PLACEHOLDER_HEADER_ENVIRONMENT = [
  { id: 'temperature', label: 'Nhiệt độ', value: '--°C' },
  { id: 'humidity', label: 'Độ ẩm', value: '--%' },
  { id: 'co2', label: 'CO₂', value: '-- ppm' },
  { id: 'light', label: 'Ánh sáng', value: '-- lux' },
]

export function formatHeaderEnvironment(telemetry, isMockMode = false) {
  if (!telemetry) {
    return isMockMode ? DEFAULT_HEADER_ENVIRONMENT : PLACEHOLDER_HEADER_ENVIRONMENT
  }

  return [
    {
      id: 'temperature',
      label: 'Nhiệt độ',
      value: telemetry.temperature != null ? `${telemetry.temperature.toFixed(1)}°C` : '--°C',
    },
    {
      id: 'humidity',
      label: 'Độ ẩm',
      value: telemetry.humidity != null ? `${Math.round(telemetry.humidity)}%` : '--%',
    },
    {
      id: 'co2',
      label: 'CO₂',
      value: telemetry.co2 != null ? `${Math.round(telemetry.co2)} ppm` : '-- ppm',
    },
    {
      id: 'light',
      label: 'Ánh sáng',
      value: telemetry.light != null ? `${Math.round(telemetry.light)} lux` : '-- lux',
    },
  ]
}
