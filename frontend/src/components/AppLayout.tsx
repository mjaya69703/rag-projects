import React from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useTheme } from '../shared/hooks'
import { Button, Icon } from '../shared/components'
import { SessionsSection, Sidebar } from './Sidebar'

export function AppLayout() {
  const location = useLocation()
  const isChat = location.pathname === '/'
  const { toggleTheme, isDark } = useTheme()

  return (
    <div className="app-shell">
      <Sidebar>
        {isChat && <SessionsSection />}
      </Sidebar>

      <div className="main-wrapper">
        <header className="top-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Workspace</span>
            <span style={{ color: 'var(--border-default)' }}>/</span>
            <span style={{ fontSize: '0.9rem', fontWeight: '600', color: 'var(--text-primary)' }}>
              {location.pathname === '/' ? 'Chat Studio' : location.pathname.replace('/', '').toUpperCase()}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Button
              variant="ghost"
              size="sm"
              icon={isDark ? 'sun' : 'moon'}
              onClick={toggleTheme}
              title={`Ganti ke ${isDark ? 'Light Mode' : 'Dark Mode'}`}
            >
              {isDark ? 'Light' : 'Dark'}
            </Button>
          </div>
        </header>

        <main className="page-body">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
