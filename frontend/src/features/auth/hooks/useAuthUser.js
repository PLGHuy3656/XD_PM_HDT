import { useAuth } from '../../../context/AuthContext'

/**
 * Convenient selector hook for authenticated user state
 */
export function useAuthUser() {
  const { user, isAuthenticated, hasRole, logout, updateProfile } = useAuth()

  return {
    user,
    isAuthenticated,
    isFarmOwner: hasRole('FARM_OWNER'),
    isTechnician: hasRole('TECHNICIAN'),
    isAdmin: hasRole('ADMIN'),
    displayName: user?.name || user?.email || 'Người dùng',
    email: user?.email || '',
    phone: user?.phone || '',
    role: user?.role || '',
    roles: user?.roles || [],
    logout,
    updateProfile,
  }
}

export default useAuthUser
