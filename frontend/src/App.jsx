import { Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './components/common/ProtectedRoute'

import LoginPage from './pages/auth/Login/LoginPage'
import RegisterPage from './pages/auth/Register/RegisterPage'

import FarmOwnerDashboardPage from './pages/farm-owner/Dashboard/DashboardPage'
import FarmOwnerEnvironmentPage from './pages/farm-owner/Environment/EnvironmentPage'

import EnvironmentControlPage from './pages/farm-owner/Environment/EnvironmentControlPage'

import FarmOwnerDevicesPage from './pages/farm-owner/Devices/DevicesPage'

import FarmOwnerSwiftletsPage from './pages/farm-owner/Swiftlets/SwiftletsPage'

import AlertsPage from './pages/farm-owner/Alerts/AlertsPage'

import TechnicianDashboardPage from './pages/technician/Dashboard/DashboardPage'

import TechnicianDevicesPage from './pages/technician/Devices/DevicesPage'

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
        path="/owner/environment"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <FarmOwnerEnvironmentPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/owner/environment/control"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <EnvironmentControlPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/owner/devices"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <FarmOwnerDevicesPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/owner/swiftlets"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <FarmOwnerSwiftletsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/owner/alerts"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <AlertsPage />
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
        path="/technician/devices"
        element={
          <ProtectedRoute allowedRoles={['TECHNICIAN']}>
            <TechnicianDevicesPage />
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