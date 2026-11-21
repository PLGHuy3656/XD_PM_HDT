import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'
import { ErrorBoundary } from '../common/feedback'
import {
  NOTIFICATION_CLICK_EVENT,
  ensureForegroundPushListeners,
} from '../../features/notifications/fcmClient.js'
import { sanitizeNotificationRoute } from '../../features/notifications/fcmConfig.js'
import './AppLayout.css'

function AppLayout({ children }) {
  const navigate = useNavigate()

  useEffect(() => {
    ensureForegroundPushListeners()
    const onNotificationClick = (event) => {
      const safeRoute = sanitizeNotificationRoute(event?.detail?.link)
      navigate(safeRoute)
    }
    window.addEventListener(NOTIFICATION_CLICK_EVENT, onNotificationClick)
    return () => window.removeEventListener(NOTIFICATION_CLICK_EVENT, onNotificationClick)
  }, [navigate])

  return (
    <div className="app-layout">
      <Sidebar />

      <div className="app-content">
        <Header />

        <main className="main-content page-container">
          <ErrorBoundary>
            {children}
          </ErrorBoundary>
        </main>
      </div>
    </div>
  )
}

export default AppLayout
