/**
 * Authentication Utilities, User Normalization, and Mock Data
 */

export const STORAGE_KEY_USER = 'swiftletcare_user'
export const STORAGE_KEY_LEGACY_USER = 'nestmate_user'
export const STORAGE_KEY_TOKEN = 'swiftletcare_token'

/**
 * Standard Mock Users for offline development and local simulation
 */
export const MOCK_USERS = [
  {
    id: 'd632d08d-2a47-46f0-8798-83fd733024c3',
    name: 'Farm Owner',
    email: 'owner@nestmate.dev',
    phone: '0901 234 567',
    password: '123456',
    role: 'FARM_OWNER',
    roles: ['FARM_OWNER'],
  },
  {
    id: 'f8812c41-7c93-4e39-b972-e1d8820c7541',
    name: 'Technician',
    email: 'tech@nestmate.dev',
    phone: '0902 345 678',
    password: '123456',
    role: 'TECHNICIAN',
    roles: ['TECHNICIAN'],
  },
  {
    id: 'a1123e44-5566-7788-99aa-bbccddeeff00',
    name: 'Administrator',
    email: 'admin@nestmate.dev',
    phone: '0903 456 789',
    password: '123456',
    role: 'ADMIN',
    roles: ['ADMIN'],
  },
]

/**
 * Normalizes user object across Backend Gateway schemas and Mock data formats
 * @param {any} raw
 * @returns {any}
 */
export function normalizeUser(raw) {
  if (!raw) return null

  const roles = Array.isArray(raw.roles)
    ? raw.roles
    : raw.role
      ? [raw.role]
      : []

  const primaryRole = roles[0] || raw.role || 'FARM_OWNER'

  return {
    id: raw.id || raw.user_id || raw.userId || 'unknown-id',
    name: raw.full_name || raw.fullName || raw.name || raw.email || 'Người dùng',
    email: raw.email || '',
    phone: raw.phone || raw.phone_number || '',
    status: raw.status || 'ACTIVE',
    role: primaryRole,
    roles,
  }
}

/**
 * Check if user possesses one or more specified roles
 * @param {any} user
 * @param {string | string[]} requiredRole
 * @returns {boolean}
 */
export function hasRole(user, requiredRole) {
  if (!user) return false
  const userRoles = Array.isArray(user.roles) ? user.roles : [user.role].filter(Boolean)
  if (Array.isArray(requiredRole)) {
    return requiredRole.some((r) => userRoles.includes(r))
  }
  return userRoles.includes(requiredRole)
}
