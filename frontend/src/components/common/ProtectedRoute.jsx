import { Navigate } from 'react-router-dom'

import { useAuth } from '../../context/AuthContext'

function getDashboardPath(role) {
  switch (role) {
    case 'FARM_OWNER':
      return '/owner/dashboard'

    case 'TECHNICIAN':
      return '/technician/dashboard'

    case 'ADMIN':
      return '/admin/dashboard'

    default:
      return '/login'
  }
}

function ProtectedRoute({ children, allowedRoles }) {
  const { user, isAuthenticated } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (
    allowedRoles &&
    !allowedRoles.includes(user.role)
  ) {
    return (
      <Navigate
        to={getDashboardPath(user.role)}
        replace
      />
    )
  }

  return children
}

export default ProtectedRoute