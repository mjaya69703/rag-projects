import { Outlet, useLocation } from 'react-router-dom'
import { PageHeaderProvider } from './PageHeader'
import { SessionsSection, Sidebar } from './Sidebar'

/** Layout global: sidebar + topbar konsisten di semua halaman. */
export function AppLayout() {
  const location = useLocation()
  const isChat = location.pathname === '/'

  return (
    <div className="app-shell">
      {isChat ? (
        <Sidebar>
          <SessionsSection />
        </Sidebar>
      ) : (
        <Sidebar />
      )}
      <main className="workspace">
        <PageHeaderProvider>
          <div className="page">{<Outlet />}</div>
        </PageHeaderProvider>
      </main>
    </div>
  )
}
