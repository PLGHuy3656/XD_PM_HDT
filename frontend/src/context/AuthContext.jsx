import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'

import { authApi, setAuthToken, setUnauthorizedHandler } from '../api'
import { USE_MOCK } from '../api/config'
import { clearActiveFarm } from '../features/farms/activeFarmStore.js'
import {
  clearForeignBrowserPushOnLogin,
  unregisterBrowserPushOnLogout,
} from '../features/notifications/fcmClient.js'
import {
  MOCK_USERS,
  STORAGE_KEY_LEGACY_USER,
  STORAGE_KEY_TOKEN,
  STORAGE_KEY_USER,
  hasRole,
  normalizeUser,
} from './authUtils'

export { hasRole, normalizeUser, MOCK_USERS }

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const stored =
      localStorage.getItem(STORAGE_KEY_USER) ||
      localStorage.getItem(STORAGE_KEY_LEGACY_USER)

    if (!stored) return null

    try {
      return normalizeUser(JSON.parse(stored))
    } catch {
      localStorage.removeItem(STORAGE_KEY_USER)
      localStorage.removeItem(STORAGE_KEY_LEGACY_USER)
      return null
    }
  })

  const [token, setTokenState] = useState(() => {
    return localStorage.getItem(STORAGE_KEY_TOKEN) || null
  })

  const [authError, setAuthError] = useState(null)

  // Sync token to API client whenever token changes or on initial mount
  useEffect(() => {
    if (token) {
      setAuthToken(token)
    } else {
      setAuthToken(null)
    }
  }, [token])

  const logout = useCallback(async () => {
    try {
      if (!USE_MOCK) {
        // INT03-R2: Unregister FCM token BEFORE revoking JWT so the previous user
        // immediately stops receiving browser push on a shared Chrome profile.
        await unregisterBrowserPushOnLogout()
        await authApi.logout()
      }
    } catch (_) {
      // Best-effort server revocation
    }
    setUser(null)
    setTokenState(null)
    setAuthToken(null)
    clearActiveFarm()
    localStorage.removeItem(STORAGE_KEY_USER)
    localStorage.removeItem(STORAGE_KEY_LEGACY_USER)
    localStorage.removeItem(STORAGE_KEY_TOKEN)
  }, [])

  // Listen for 401 Unauthorized from API Client
  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout()
      setAuthError('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.')
    })
  }, [logout])

  /**
   * Unified Login Handler:
   * When USE_MOCK is false, calls Real API Gateway POST /api/auth/login.
   * When USE_MOCK is true, verifies credentials against MOCK_USERS locally.
   */
  const login = async (email, password) => {
    const normalizedEmail = email?.trim()?.toLowerCase() || ''
    setAuthError(null)

    if (USE_MOCK) {
      // Mock mode authentication
      const matched = MOCK_USERS.find(
        (item) => item.email.toLowerCase() === normalizedEmail && item.password === password,
      )

      if (!matched) {
        return {
          success: false,
          message: 'Email hoặc mật khẩu không chính xác (Chế độ mô phỏng).',
        }
      }

      const authenticatedUser = normalizeUser(matched)
      const mockToken = `mock-token-${authenticatedUser.role.toLowerCase()}-${authenticatedUser.id}`

      setUser(authenticatedUser)
      setTokenState(mockToken)
      setAuthToken(mockToken)

      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(authenticatedUser))
      localStorage.setItem(STORAGE_KEY_LEGACY_USER, JSON.stringify(authenticatedUser))
      localStorage.setItem(STORAGE_KEY_TOKEN, mockToken)

      return {
        success: true,
        user: authenticatedUser,
      }
    }

    // Real API Gateway authentication
    try {
      const response = await authApi.login({
        email: normalizedEmail,
        password,
      })

      const accessToken = response?.access_token || response?.accessToken
      if (!accessToken) {
        return {
          success: false,
          message: 'Máy chủ phản hồi thiếu access_token xác thực.',
        }
      }

      const rawUser = response?.user || {
        email: normalizedEmail,
        role: 'FARM_OWNER',
        name: normalizedEmail.split('@')[0],
      }
      const authenticatedUser = normalizeUser(rawUser)
      await clearForeignBrowserPushOnLogin(authenticatedUser.id)

      setUser(authenticatedUser)
      setTokenState(accessToken)
      setAuthToken(accessToken)

      localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(authenticatedUser))
      localStorage.setItem(STORAGE_KEY_LEGACY_USER, JSON.stringify(authenticatedUser))
      localStorage.setItem(STORAGE_KEY_TOKEN, accessToken)

      return {
        success: true,
        user: authenticatedUser,
      }
    } catch (err) {
      return {
        success: false,
        message: err?.message || 'Đăng nhập không thành công. Vui lòng thử lại.',
      }
    }
  }

  const updateProfile = (profileData) => {
    if (!user) {
      return {
        success: false,
        message: 'Không tìm thấy phiên đăng nhập.',
      }
    }

    const updatedUser = {
      ...user,
      name: profileData.name?.trim() || user.name,
      phone: profileData.phone?.trim() || '',
    }

    setUser(updatedUser)
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(updatedUser))
    localStorage.setItem(STORAGE_KEY_LEGACY_USER, JSON.stringify(updatedUser))

    return {
      success: true,
      user: updatedUser,
    }
  }

  const value = {
    user,
    token,
    authError,
    isAuthenticated: Boolean(user),
    hasRole: (roleOrRoles) => hasRole(user, roleOrRoles),
    login,
    logout,
    updateProfile,
    isMockMode: USE_MOCK,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

export default AuthContext
