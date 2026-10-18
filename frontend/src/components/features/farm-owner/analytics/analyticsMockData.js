export const analyticsFarms = [
  {
    id: 'farm-01',
    name: 'Nhà yến Bình Chánh',
    zones: [
      { id: 'all', name: 'Tất cả khu vực' },
      { id: 'zone-a', name: 'Khu vực A · Cửa chính' },
      { id: 'zone-b', name: 'Khu vực B · Tầng 2' },
    ],
  },
]

export const birdPerformance = {
  entries: 428,
  exits: 391,
  returnRate: 93.6,
  difference: 37,
  change: 8.4,
}

export const hourlyBirdActivity = [
  { label: '05h', entries: 184, exits: 326 },
  { label: '07h', entries: 142, exits: 412 },
  { label: '09h', entries: 206, exits: 238 },
  { label: '11h', entries: 231, exits: 196 },
  { label: '13h', entries: 258, exits: 172 },
  { label: '15h', entries: 284, exits: 151 },
  { label: '17h', entries: 391, exits: 118 },
  { label: '19h', entries: 428, exits: 96 },
  { label: '21h', entries: 317, exits: 82 },
]

export const zoneDensity = [
  {
    id: 'zone-a',
    name: 'Khu vực A',
    description: 'Cửa chính',
    value: 92,
  },
  {
    id: 'zone-b',
    name: 'Khu vực B',
    description: 'Tầng 2',
    value: 84,
  },
]

export const microClimateScores = [
  {
    id: 'zone-a',
    name: 'Khu vực A',
    score: 91,
    status: 'Tốt',
  },
  {
    id: 'zone-b',
    name: 'Khu vực B',
    score: 84,
    status: 'Ổn định',
  },
]

export const alertDistribution = [
  {
    severity: 'CRITICAL',
    count: 2,
  },
  {
    severity: 'HIGH',
    count: 4,
  },
  {
    severity: 'MEDIUM',
    count: 7,
  },
  {
    severity: 'LOW',
    count: 3,
  },
]
export const environmentMetrics = [
  {
    id: 'temperature',
    label: 'Nhiệt độ',
    unit: '°C',
  },
  {
    id: 'humidity',
    label: 'Độ ẩm',
    unit: '%',
  },
  {
    id: 'co2',
    label: 'CO₂',
    unit: 'ppm',
  },
  {
    id: 'light',
    label: 'Ánh sáng',
    unit: 'lux',
  },
  {
    id: 'audio',
    label: 'Âm thanh',
    unit: 'dB',
  },
]

export const analyticsPeriods = [
  { id: '1h', label: '1 giờ' },
  { id: '6h', label: '6 giờ' },
  { id: '24h', label: '24 giờ' },
  { id: '7d', label: '7 ngày' },
  { id: '30d', label: '30 ngày' },
]

export const environmentComparison = {
  temperature: [
    {
      label: '00h',
      zoneA: 27.2,
      zoneB: 27.8,
    },
    {
      label: '04h',
      zoneA: 26.8,
      zoneB: 27.4,
    },
    {
      label: '08h',
      zoneA: 28.1,
      zoneB: 28.6,
    },
    {
      label: '12h',
      zoneA: 29.4,
      zoneB: 30.1,
    },
    {
      label: '16h',
      zoneA: 30.2,
      zoneB: 30.8,
    },
    {
      label: '20h',
      zoneA: 28.7,
      zoneB: 29.3,
    },
    {
      label: '24h',
      zoneA: 27.9,
      zoneB: 28.4,
    },
  ],

  humidity: [
    {
      label: '00h',
      zoneA: 82,
      zoneB: 79,
    },
    {
      label: '04h',
      zoneA: 84,
      zoneB: 81,
    },
    {
      label: '08h',
      zoneA: 80,
      zoneB: 78,
    },
    {
      label: '12h',
      zoneA: 77,
      zoneB: 75,
    },
    {
      label: '16h',
      zoneA: 76,
      zoneB: 73,
    },
    {
      label: '20h',
      zoneA: 79,
      zoneB: 76,
    },
    {
      label: '24h',
      zoneA: 81,
      zoneB: 78,
    },
  ],

  co2: [
    {
      label: '00h',
      zoneA: 590,
      zoneB: 610,
    },
    {
      label: '04h',
      zoneA: 605,
      zoneB: 625,
    },
    {
      label: '08h',
      zoneA: 620,
      zoneB: 648,
    },
    {
      label: '12h',
      zoneA: 655,
      zoneB: 682,
    },
    {
      label: '16h',
      zoneA: 671,
      zoneB: 704,
    },
    {
      label: '20h',
      zoneA: 638,
      zoneB: 661,
    },
    {
      label: '24h',
      zoneA: 612,
      zoneB: 635,
    },
  ],

  light: [
    {
      label: '00h',
      zoneA: 18,
      zoneB: 14,
    },
    {
      label: '04h',
      zoneA: 15,
      zoneB: 12,
    },
    {
      label: '08h',
      zoneA: 82,
      zoneB: 67,
    },
    {
      label: '12h',
      zoneA: 124,
      zoneB: 98,
    },
    {
      label: '16h',
      zoneA: 108,
      zoneB: 86,
    },
    {
      label: '20h',
      zoneA: 46,
      zoneB: 39,
    },
    {
      label: '24h',
      zoneA: 21,
      zoneB: 17,
    },
  ],

  audio: [
    {
      label: '00h',
      zoneA: 48,
      zoneB: 45,
    },
    {
      label: '04h',
      zoneA: 46,
      zoneB: 44,
    },
    {
      label: '08h',
      zoneA: 57,
      zoneB: 53,
    },
    {
      label: '12h',
      zoneA: 61,
      zoneB: 58,
    },
    {
      label: '16h',
      zoneA: 64,
      zoneB: 60,
    },
    {
      label: '20h',
      zoneA: 59,
      zoneB: 55,
    },
    {
      label: '24h',
      zoneA: 51,
      zoneB: 48,
    },
  ],
}

export const birdTrendAnalytics = [
  {
    label: '10/10',
    entries: 362,
    exits: 348,
  },
  {
    label: '11/10',
    entries: 381,
    exits: 355,
  },
  {
    label: '12/10',
    entries: 374,
    exits: 361,
  },
  {
    label: '13/10',
    entries: 405,
    exits: 372,
  },
  {
    label: '14/10',
    entries: 397,
    exits: 380,
  },
  {
    label: '15/10',
    entries: 416,
    exits: 386,
  },
  {
    label: '16/10',
    entries: 428,
    exits: 391,
  },
]

export const returnRateCorrelation = [
  {
    label: 'Khu vực A',
    humidity: 82,
    returnRate: 95.2,
  },
  {
    label: 'Khu vực B',
    humidity: 78,
    returnRate: 91.8,
  },
]

export const alertTrend = [
  {
    label: '10/10',
    critical: 0,
    high: 1,
    medium: 2,
    low: 1,
  },
  {
    label: '11/10',
    critical: 1,
    high: 0,
    medium: 1,
    low: 0,
  },
  {
    label: '12/10',
    critical: 0,
    high: 2,
    medium: 1,
    low: 1,
  },
  {
    label: '13/10',
    critical: 0,
    high: 1,
    medium: 0,
    low: 1,
  },
  {
    label: '14/10',
    critical: 1,
    high: 0,
    medium: 1,
    low: 0,
  },
  {
    label: '15/10',
    critical: 0,
    high: 0,
    medium: 1,
    low: 0,
  },
  {
    label: '16/10',
    critical: 0,
    high: 0,
    medium: 1,
    low: 0,
  },
]
export const yieldSummary = {
  totalNests: 1268,
  harvestedNests: 184,
  currentYield: 14.8,
  previousYield: 13.2,
  yieldChange: 12.1,
}

export const yieldTrend = [
  { label: 'T5', value: 10.4 },
  { label: 'T6', value: 11.2 },
  { label: 'T7', value: 12.6 },
  { label: 'T8', value: 12.1 },
  { label: 'T9', value: 13.2 },
  { label: 'T10', value: 14.8 },
]

export const zoneYield = [
  {
    id: 'zone-a',
    name: 'Khu vực A',
    description: 'Cửa chính',
    nests: 684,
    harvested: 102,
    yield: 8.3,
    contribution: 56,
  },
  {
    id: 'zone-b',
    name: 'Khu vực B',
    description: 'Tầng 2',
    nests: 584,
    harvested: 82,
    yield: 6.5,
    contribution: 44,
  },
]

export const harvestHistory = [
  {
    id: 'HAR-005',
    date: '12/10/2026',
    zone: 'Khu vực A',
    nests: 38,
    yield: 3.1,
    note: 'Thu hoạch định kỳ',
  },
  {
    id: 'HAR-004',
    date: '28/09/2026',
    zone: 'Khu vực B',
    nests: 31,
    yield: 2.4,
    note: 'Thu hoạch định kỳ',
  },
  {
    id: 'HAR-003',
    date: '14/09/2026',
    zone: 'Khu vực A',
    nests: 35,
    yield: 2.8,
    note: 'Thu hoạch định kỳ',
  },
  {
    id: 'HAR-002',
    date: '30/08/2026',
    zone: 'Khu vực B',
    nests: 28,
    yield: 2.2,
    note: 'Thu hoạch định kỳ',
  },
  {
    id: 'HAR-001',
    date: '16/08/2026',
    zone: 'Khu vực A',
    nests: 33,
    yield: 2.7,
    note: 'Thu hoạch định kỳ',
  },
]