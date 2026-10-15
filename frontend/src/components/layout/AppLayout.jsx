import Header from './Header'
import Sidebar from './Sidebar'
import './AppLayout.css'

function AppLayout({ children }) {
  return (
    <div className="app-layout">
      <Sidebar />

      <div className="app-content">
        <Header />

        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  )
}

export default AppLayout