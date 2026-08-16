import React, { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useTheme } from '../shared/hooks'
import { usePWA } from '../context/PWAContext'
import { Button, Icon } from '../shared/components'
import { MobileBottomNav } from './MobileBottomNav'
import { SessionsSection, Sidebar } from './Sidebar'

export function AppLayout() {
  const location = useLocation()
  const isChat = location.pathname === '/'
  const { toggleTheme, isDark } = useTheme()
  const { isInstallable, isInstalled, isIOS, promptInstall } = usePWA()
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)

  const getPageTitle = () => {
    switch (location.pathname) {
      case '/':
        return 'Chat Studio'
      case '/library':
        return 'Knowledge Library'
      case '/flashcards':
        return '3D Flashcards'
      case '/quiz':
        return 'AI Quiz Arena'
      case '/glossary':
        return 'Glosarium'
      case '/progress':
        return 'Diagnostik & Progress'
      case '/settings':
        return 'Pengaturan'
      default:
        return location.pathname.replace('/', '').toUpperCase()
    }
  }

  return (
    <div className="app-shell">
      <Sidebar isOpen={isSidebarOpen} onClose={() => setIsSidebarOpen(false)}>
        {isChat && <SessionsSection onSelect={() => setIsSidebarOpen(false)} />}
      </Sidebar>

      <div className="main-wrapper">
        <header className="top-bar">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            {/* Hamburger Button on Mobile */}
            <button
              type="button"
              className="mobile-menu-toggle"
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              aria-label="Toggle Menu"
            >
              <Icon name={isSidebarOpen ? 'x' : 'menu'} size={20} />
            </button>

            <span className="top-bar-breadcrumb-parent" style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Workspace
            </span>
            <span className="top-bar-breadcrumb-parent" style={{ color: 'var(--border-default)' }}>/</span>
            <span style={{ fontSize: '0.9rem', fontWeight: '700', color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
              {getPageTitle()}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            {/* PWA Install Button */}
            {(!isInstalled && (isInstallable || isIOS)) && (
              <Button
                variant="glass"
                size="sm"
                icon="download"
                onClick={() => void promptInstall()}
                title="Pasang aplikasi ke perangkat Anda"
                className="pwa-install-header-btn"
              >
                Install App
              </Button>
            )}

            <Button
              variant="ghost"
              size="sm"
              icon={isDark ? 'sun' : 'moon'}
              onClick={toggleTheme}
              title={`Ganti ke ${isDark ? 'Light Mode' : 'Dark Mode'}`}
            >
              <span className="theme-btn-label">{isDark ? 'Light' : 'Dark'}</span>
            </Button>
          </div>
        </header>

        <main className="page-body">
          <Outlet />
        </main>

        {/* Bottom Navigation for Mobile */}
        <MobileBottomNav
          onOpenMenu={() => setIsSidebarOpen(!isSidebarOpen)}
          isMenuOpen={isSidebarOpen}
        />
      </div>
    </div>
  )
}

