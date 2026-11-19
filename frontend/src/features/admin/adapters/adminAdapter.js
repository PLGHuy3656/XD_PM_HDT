/**
 * Admin Domain Adapters
 * Normalizes backend DTOs from Management Service, Gateway, and IoT Service
 * into presentation models expected by the 5 Admin UI screens.
 */

export const ADMIN_ROLE_LABELS = {
  ADMIN: 'Administrator',
  TECHNICIAN: 'Technician',
  FARM_OWNER: 'Farm Owner',
}

export const ADMIN_ROLE_DESCRIPTIONS = {
  ADMIN: 'Quản trị nền tảng',
  TECHNICIAN: 'Thiết bị và hỗ trợ kỹ thuật',
  FARM_OWNER: 'Quản lý và vận hành nhà yến',
}

export const ADMIN_DEVICE_TYPE_LABELS = {
  ENVIRONMENT_MONITOR: 'Environment Sensor',
  CAMERA: 'AI Camera Node',
  CONTROLLER: 'ESP32 Controller',
  ACTUATOR: 'Actuator Control',
  AUDIO_MONITOR: 'Audio Monitor',
}

/**
 * Normalizes device DTO from Management Service /devices endpoint
 * @param {Object} raw - Device object from backend
 * @param {Object} [farmsMap] - Map of farmId -> farm
 * @returns {Object} Normalized admin device
 */
export function normalizeAdminDevice(raw, farmsMap = {}) {
  if (!raw) return null

  const deviceId = raw.device_id || raw.id || ''
  const nodeId = raw.node_id || deviceId
  const rawType = raw.device_type || 'UNKNOWN'
  const displayType = ADMIN_DEVICE_TYPE_LABELS[rawType] || rawType
  const status = raw.status === 'ONLINE' ? 'ONLINE' : 'OFFLINE'
  const farmInfo = farmsMap[raw.farm_id] || {}
  const isZoneAssigned = Boolean(raw.zone_id)

  return {
    id: nodeId || deviceId,
    deviceId,
    nodeId,
    name: raw.name || nodeId || 'Thiết bị không tên',
    type: displayType,
    rawType,
    status,
    isZoneAssigned,
    ipAddress: raw.ip_address || '--',
    firmwareVersion: raw.firmware_version || '--',
    createdAt: raw.created_at || null,
    farm: {
      id: raw.farm_id || '',
      code: farmInfo.code || farmInfo.farm_code || raw.farm_id || '--',
      name: farmInfo.name || farmInfo.farm_name || 'Nhà yến',
    },
    farmTechnician: farmInfo.technician_name || farmInfo.technician_id
      ? {
          id: farmInfo.technician_id || null,
          name: farmInfo.technician_name || 'Kỹ thuật viên',
          email: farmInfo.technician_email || '--',
        }
      : null,
    zone: {
      id: raw.zone_id || 'unassigned',
      name: isZoneAssigned ? (raw.zone_name || 'Khu vực') : 'Chưa phân bổ Zone',
      floor: raw.floor || (isZoneAssigned ? '--' : 'Chưa gán'),
    },
    provisioning: status === 'ONLINE' ? 'PROVISIONED' : 'DISCONNECTED',
  }
}

/**
 * Normalizes farm DTO from Management Service /api/farms endpoint
 * Attaches associated zones and devices to preserve getFarmDeviceCount compatibility.
 * @param {Object} raw - Farm object from backend
 * @param {Array} [zones] - Zones belonging to this farm
 * @param {Array} [devices] - Devices belonging to this farm
 * @returns {Object} Normalized admin farm
 */
export function normalizeAdminFarm(raw, zones = [], devices = []) {
  if (!raw) return null

  const farmId = raw.farm_id || raw.id || ''
  const farmDevices = (devices || []).filter((d) => d.farm?.id === farmId || d.farm_id === farmId)

  // Map real zones with devices nested under them
  const mappedZones = (zones || []).map((zone) => {
    const zoneId = zone.zone_id || zone.id
    const zoneDevices = farmDevices.filter((d) => d.zone?.id === zoneId || d.zone_id === zoneId)
    return {
      id: zoneId,
      code: zone.zone_code || '--',
      name: zone.name || zone.zone_name || `Khu vực ${zone.zone_code || ''}`,
      floor: zone.zone_code || zone.floor || '--',
      status: 'STABLE',
      devices: zoneDevices,
    }
  })

  // Keep unassigned-zone devices separate instead of fabricating a fake zone
  const unassignedDevices = farmDevices.filter(
    (d) => !d.zone?.id || d.zone?.id === 'unassigned' || !zones.some((z) => (z.zone_id || z.id) === d.zone?.id)
  )

  const hasTechnician = Boolean(raw.technician_name || raw.technician_id)
  const hasOwner = Boolean(raw.owner_id || raw.owner_name)

  return {
    id: farmId,
    code: raw.farm_code || raw.code || '--',
    name: raw.farm_name || raw.name || 'Nhà yến',
    address: raw.address || '--',
    status: raw.status || 'ACTIVE',
    approvalStatus: raw.approval_status || 'APPROVED',
    rejectionReason: raw.rejection_reason || null,
    approvedBy: raw.approved_by || null,
    approvedAt: raw.approved_at || null,
    health: 'GOOD',
    owner: hasOwner
      ? {
          id: raw.owner_id || '--',
          name: raw.owner_name || 'Chủ nhà yến',
          email: raw.owner_email || '--',
          phone: raw.owner_phone || '--',
        }
      : null,
    technician: hasTechnician
      ? {
          id: raw.technician_id,
          name: raw.technician_name || 'Kỹ thuật viên',
          email: raw.technician_email || '--',
          phone: raw.technician_phone || '--',
          status: 'ASSIGNED',
        }
      : null,
    zones: mappedZones,
    unassignedDevices,
    zoneCount: raw.zone_count ?? mappedZones.length,
    deviceCount: raw.device_count ?? farmDevices.length,
    createdAt: raw.created_at || null,
  }
}

/**
 * Normalizes technician DTO from Management Service /api/technicians
 * @param {Object} raw - Technician object
 * @returns {Object} Normalized technician
 */
export function normalizeAdminTechnician(raw) {
  if (!raw) return null

  return {
    id: raw.technician_id || raw.id,
    name: raw.full_name || raw.name || 'Kỹ thuật viên',
    email: raw.email || '--',
    phone: raw.phone || '--',
    role: 'TECHNICIAN',
    status: raw.status || 'ACTIVE',
    joinedAt: '01/11/2026',
    lastActive: 'Đang hoạt động',
  }
}

/**
 * Normalizes authenticated current user into an admin user presentation record
 * @param {Object} user - User object from authApi.getProfile()
 * @returns {Object} Normalized admin user
 */
export function normalizeAdminUser(user) {
  if (!user) return null

  const roles = user.roles || []
  const primaryRole = roles.includes('ADMIN')
    ? 'ADMIN'
    : roles.includes('TECHNICIAN')
      ? 'TECHNICIAN'
      : 'FARM_OWNER'

  return {
    id: user.id || 'ADMIN-001',
    name: user.full_name || 'Quản trị viên',
    email: user.email || '',
    phone: user.phone || '--',
    role: primaryRole,
    status: user.status || 'ACTIVE',
    joinedAt: '01/11/2026',
    lastActive: 'Vừa xong',
  }
}

/**
 * Normalizes Gateway /health response into System Overview service list
 * @param {Object} healthData - Raw /health payload
 * @returns {Array} List of normalized system services
 */
export function normalizeSystemServices(healthData, { managementOk = true, alertsOk = false } = {}) {
  const isGatewayUp = Boolean(healthData && healthData.status === 'ok')
  const upstreams = healthData?.upstreams || {}
  const isRemoteUpstream = (key) =>
    typeof upstreams[key] === 'string' &&
    upstreams[key].length > 0 &&
    !upstreams[key].includes('127.0.0.1') &&
    !upstreams[key].includes('localhost')

  const iotDeployed = isGatewayUp && isRemoteUpstream('iot')
  const aiDeployed = isGatewayUp && isRemoteUpstream('ai')
  const notifDeployed = isGatewayUp && (alertsOk || isRemoteUpstream('notification'))
  const analyticsDeployed = isGatewayUp && isRemoteUpstream('analytics')

  return [
    {
      id: 'api-gateway',
      name: 'API Gateway (:8000)',
      description: 'Điểm truy cập trung tâm, JWT Authentication & Reverse Proxy',
      status: isGatewayUp ? 'HEALTHY' : 'DOWN',
      latency: isGatewayUp ? 'Online' : null,
      tier: 'CURRENT',
    },
    {
      id: 'management',
      name: 'Management Service (:8001)',
      description: 'Quản lý Farm, Zone, Device, Identity & RBAC',
      status: managementOk ? 'HEALTHY' : 'DOWN',
      latency: managementOk ? 'Online' : null,
      tier: 'CURRENT',
    },
    {
      id: 'iot',
      name: 'IoT Service (:8002)',
      description: 'Xử lý kết nối thiết bị MQTT, Presence & Telemetry',
      status: iotDeployed ? 'HEALTHY' : 'PLANNED',
      latency: iotDeployed ? 'Online' : null,
      tier: iotDeployed ? 'CURRENT' : 'PLANNED',
    },
    {
      id: 'ai-vision',
      name: 'AI Vision Service (:8003)',
      description: 'Nhận diện chim yến, thiên địch và đếm lượt qua camera',
      status: aiDeployed ? 'HEALTHY' : 'PLANNED',
      latency: aiDeployed ? 'Online' : null,
      tier: aiDeployed ? 'CURRENT' : 'PLANNED',
    },
    {
      id: 'notification',
      name: 'Notification Service (:8004)',
      description: 'Hệ thống cảnh báo thời gian thực & Push alerts',
      status: notifDeployed ? (alertsOk ? 'HEALTHY' : 'DOWN') : 'PLANNED',
      latency: notifDeployed && alertsOk ? 'Online' : null,
      tier: notifDeployed ? 'CURRENT' : 'PLANNED',
    },
    {
      id: 'analytics',
      name: 'Analytics Service (:8005)',
      description: 'Tổng hợp số liệu & phân tích xu hướng môi trường nhà yến',
      status: analyticsDeployed ? 'HEALTHY' : 'PLANNED',
      latency: analyticsDeployed ? 'Online' : null,
      tier: analyticsDeployed ? 'CURRENT' : 'PLANNED',
    },
  ]
}

/**
 * Normalizes full admin stats for Dashboard
 * @param {Object} params
 * @returns {Object} { managementItems, roles, recentAccounts, services }
 */
export function normalizeAdminDashboardStats({
  farms = [],
  devices = [],
  users = [],
  healthData = null,
  services: precomputedServices = null,
}) {
  const activeUsersCount = users.filter((u) => u.status === 'ACTIVE').length
  const activeFarmsCount = farms.filter((f) => f.status === 'ACTIVE').length
  const totalZonesCount = farms.reduce((acc, f) => acc + (f.zoneCount || f.zones?.length || 0), 0)
  const onlineDevicesCount = devices.filter((d) => d.status === 'ONLINE').length

  const managementItems = [
    {
      id: 'users',
      eyebrow: 'USER & ACCESS',
      value: String(users.length),
      title: 'Users & Roles',
      description: `${activeUsersCount} tài khoản đang hoạt động`,
      icon: '◎',
      path: '/admin/users',
    },
    {
      id: 'farms',
      eyebrow: 'FARM MANAGEMENT',
      value: String(farms.length),
      title: 'Nhà yến',
      description: `${activeFarmsCount} nhà yến · ${totalZonesCount} khu vực`,
      icon: '⌂',
      path: '/admin/farms',
    },
    {
      id: 'devices',
      eyebrow: 'DEVICE REGISTRY',
      value: String(devices.length),
      title: 'Thiết bị',
      description: `${onlineDevicesCount} thiết bị đang online`,
      icon: '▣',
      path: '/admin/devices',
    },
  ]

  const roleDistribution = [
    {
      id: 'owner',
      label: 'Farm Owner',
      description: ADMIN_ROLE_DESCRIPTIONS.FARM_OWNER,
      value: users.filter((u) => u.role === 'FARM_OWNER').length,
      icon: 'FO',
    },
    {
      id: 'technician',
      label: 'Technician',
      description: ADMIN_ROLE_DESCRIPTIONS.TECHNICIAN,
      value: users.filter((u) => u.role === 'TECHNICIAN').length,
      icon: 'TE',
    },
    {
      id: 'admin',
      label: 'Administrator',
      description: ADMIN_ROLE_DESCRIPTIONS.ADMIN,
      value: users.filter((u) => u.role === 'ADMIN').length,
      icon: 'AD',
    },
  ]

  const recentAccounts = users.slice(0, 5).map((u) => ({
    id: u.id,
    name: u.name,
    email: u.email,
    role: ADMIN_ROLE_LABELS[u.role] || u.role,
    time: u.joinedAt || '01/11/2026',
  }))

  const services = precomputedServices || normalizeSystemServices(healthData)

  return {
    managementItems,
    roles: roleDistribution,
    recentAccounts,
    services,
  }
}
