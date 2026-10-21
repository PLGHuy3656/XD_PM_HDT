export const farms = [
  {
    id: 'farm-binh-an',
    name: 'Nhà yến Bình An',
    zones: [
      { id: 'zone-a', name: 'Khu vực A · Cửa chính' },
      { id: 'zone-b', name: 'Khu vực B · Tầng 2' },
    ],
  },
]

export const birdStats = {
  entries: 428,
  exits: 391,
  returnRate: 93.6,
  entriesDelta: 8.4,
  exitsDelta: 3.1,
}

export const trendData = {
  7: [
    { label: '10/10', entries: 362, exits: 348 },
    { label: '11/10', entries: 381, exits: 355 },
    { label: '12/10', entries: 374, exits: 361 },
    { label: '13/10', entries: 405, exits: 372 },
    { label: '14/10', entries: 397, exits: 380 },
    { label: '15/10', entries: 416, exits: 386 },
    { label: '16/10', entries: 428, exits: 391 },
  ],
}

export const aiEvents = [
  {
    id: 'EVT-1042',
    type: 'ENTRY',
    title: 'Đàn chim về tổ',
    location: 'Khu vực A · Cửa chính',
    time: '18:05 hôm nay',
    confidence: 98.4,
    status: 'normal',
  },
  {
    id: 'EVT-1041',
    type: 'EXIT',
    title: 'Chim xuất đàn buổi sáng',
    location: 'Khu vực A · Cửa chính',
    time: '05:42 hôm nay',
    confidence: 96.1,
    status: 'normal',
  },
  {
    id: 'EVT-1040',
    type: 'PREDATOR',
    title: 'Phát hiện cú gần cửa vào',
    location: 'Khu vực B · Tầng 2',
    time: '23:14 hôm qua',
    confidence: 88.5,
    status: 'critical',
  },
  {
    id: 'EVT-1039',
    type: 'AUDIO',
    title: 'Âm thanh bất thường',
    location: 'Khu vực A · Cửa chính',
    time: '21:36 hôm qua',
    confidence: 84.7,
    status: 'warning',
  },
]
export const cameras = [
  {
    id: 'CAM-01',
    name: 'Lối vào chính',
    zoneId: 'zone-a',
    zoneName: 'Khu vực A',
    node: 'EDGE-01',
    status: 'ONLINE',
    resolution: '1080p',
    detections: [
      {
        id: 'DET-01',
        label: 'Swiftlet',
        confidence: 96,
        className: 'bird-one',
      },
      {
        id: 'DET-02',
        label: 'Swiftlet',
        confidence: 93,
        className: 'bird-two',
      },
      {
        id: 'DET-03',
        label: 'Swiftlet',
        confidence: 91,
        className: 'bird-three',
      },
    ],
  },
  {
    id: 'CAM-02',
    name: 'Lối vào phụ',
    zoneId: 'zone-b',
    zoneName: 'Khu vực B',
    node: 'EDGE-02',
    status: 'ONLINE',
    resolution: '1080p',
    detections: [
      {
        id: 'DET-04',
        label: 'Swiftlet',
        confidence: 94,
        className: 'bird-two',
      },
      {
        id: 'DET-05',
        label: 'Swiftlet',
        confidence: 89,
        className: 'bird-one',
      },
    ],
  },
  {
    id: 'CAM-03',
    name: 'Tầng 2',
    zoneId: 'zone-b',
    zoneName: 'Khu vực B',
    node: 'EDGE-03',
    status: 'OFFLINE',
    resolution: '1080p',
    detections: [],
  },
]
