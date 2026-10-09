import { Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './components/common/ProtectedRoute'

import LoginPage from './pages/auth/Login/LoginPage'
import RegisterPage from './pages/auth/Register/RegisterPage'

import FarmOwnerDashboardPage from './pages/farm-owner/Dashboard/DashboardPage'
import TechnicianDashboardPage from './pages/technician/Dashboard/DashboardPage'
import AdminDashboardPage from './pages/admin/Dashboard/DashboardPage'

function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={<Navigate to="/login" replace />}
      />

      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route
        path="/register"
        element={<RegisterPage />}
      />

      <Route
        path="/owner/dashboard"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <FarmOwnerDashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/technician/dashboard"
        element={
          <ProtectedRoute allowedRoles={['TECHNICIAN']}>
            <TechnicianDashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/dashboard"
        element={
          <ProtectedRoute allowedRoles={['ADMIN']}>
            <AdminDashboardPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="*"
        element={<Navigate to="/login" replace />}
      />
    </Routes>
  )
}

export default App