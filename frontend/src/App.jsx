import { Navigate, Route, Routes } from 'react-router-dom'

import ProtectedRoute from './components/common/ProtectedRoute'

import LoginPage from './pages/auth/Login/LoginPage'
import RegisterPage from './pages/auth/Register/RegisterPage'
import SettingsPage from './pages/account/Settings/SettingsPage'

import FarmOwnerDashboardPage from './pages/farm-owner/Dashboard/DashboardPage'
import FarmsPage from './pages/farm-owner/Farms/FarmsPage'
import FarmOwnerEnvironmentPage from './pages/farm-owner/Environment/EnvironmentPage'
import EnvironmentControlPage from './pages/farm-owner/Environment/EnvironmentControlPage'
import FarmOwnerDevicesPage from './pages/farm-owner/Devices/DevicesPage'
import FarmOwnerSwiftletsPage from './pages/farm-owner/Swiftlets/SwiftletsPage'
import AlertsPage from './pages/farm-owner/Alerts/AlertsPage'
import AnalyticsPage from './pages/farm-owner/Analytics/AnalyticsPage'

import TechnicianDashboardPage from './pages/technician/Dashboard/DashboardPage'
import TechnicianDevicesPage from './pages/technician/Devices/DevicesPage'
import TechnicianDiagnosticsPage from './pages/technician/Diagnostics/DiagnosticsPage'
import TechnicianEnvironmentPage from './pages/technician/Environment/EnvironmentPage'

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
        path="/settings"
        element={
          <ProtectedRoute
            allowedRoles={[
              'FARM_OWNER',
              'TECHNICIAN',
              'ADMIN',
            ]}
          >
            <SettingsPage />
          </ProtectedRoute>
        }
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
        path="/owner/farms"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <FarmsPage />
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
        path="/owner/analytics"
        element={
          <ProtectedRoute allowedRoles={['FARM_OWNER']}>
            <AnalyticsPage />
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
        path="/technician/diagnostics"
        element={
          <ProtectedRoute allowedRoles={['TECHNICIAN']}>
            <TechnicianDiagnosticsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/technician/environment"
        element={
          <ProtectedRoute allowedRoles={['TECHNICIAN']}>
            <TechnicianEnvironmentPage />
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