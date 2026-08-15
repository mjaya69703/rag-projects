import React, { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useSessions } from '../context/SessionsContext'
import { useHealthStatus } from '../hooks/useHealthStatus'
import { Badge, Button, Icon, type IconName } from '../shared/components'

interface NavMenuItem {
  to: string
  label: string
  icon: IconName
}

const NAV_ITEMS: NavMenuItem[] = [
  { to: '/', label: 'Chat Studio', icon: 'chat' },
  { to: '/library', label: 'Knowledge Library', icon: 'library' },
  { to: '/flashcards', label: '3D Flashcards', icon: 'cards' },
  { to: '/quiz', label: 'AI Quiz Arena', icon: 'quiz' },
  { to: '/glossary', label: 'Glosarium', icon: 'glossary' },
  { to: '/progress', label: 'Diagnostik & Progress', icon: 'progress' },
  { to: '/settings', label: 'Pengaturan', icon: 'settings' },
]

export function Sidebar({ children }: { children?: React.ReactNode }) {
  const { createSession } = useSessions()
  const { status, retry } = useHealthStatus()
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    if (creating) return
    setCreating(true)
    try {
      await createSession()
    } finally {
      setCreating(false)
    }
  }

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div className="brand-row">
        <NavLink to="/" className="brand-logo">
          <div className="brand-icon-wrap">
            <Icon name="brain" size={20} />
          </div>
          <div>
            <div style={{ lineHeight: '1.2' }}>Cortex AI</div>
            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: '500' }}>Knowledge Studio</div>
          </div>
        </NavLink>
      </div>

      {/* New Chat CTA */}
      <button className="new-chat-btn" onClick={handleCreate} disabled={creating}>
        <Icon name="plus" size={16} />
        <span>{creating ? 'Membuat...' : 'Chat Baru'}</span>
      </button>

      {/* Main Navigation Menu */}
      <nav className="nav-menu">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            end={item.to === '/'}
          >
            <Icon name={item.icon} size={18} />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Custom Section (Sessions on Chat page) */}
      {children}

      {/* Sidebar Footer */}
      <div className="sidebar-bottom">
        <div className="status-pill" onClick={() => void retry()} style={{ cursor: 'pointer' }}>
          <div
            className="status-indicator"
            style={{
              background: status === 'connected' ? 'var(--success)' : status === 'degraded' ? 'var(--warning)' : 'var(--error)',
              boxShadow: status === 'connected' ? '0 0 8px var(--success)' : 'none',
            }}
          />
          <span>{status === 'connected' ? 'API Terhubung' : status === 'degraded' ? 'Degraded' : 'Offline'}</span>
        </div>
        <Badge variant="neutral" size="sm">v3.0.0</Badge>
      </div>
    </aside>
  )
}

export function SessionsSection() {
  const { sessions, activeId, selectSession } = useSessions()

  return (
    <div className="sidebar-sessions">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 0.5rem' }}>
        <span className="sessions-title">Riwayat Chat</span>
        <Badge variant="neutral" size="sm">{sessions.length}</Badge>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
        {sessions.length === 0 ? (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', padding: '0.5rem 0.75rem' }}>
            Belum ada riwayat percakapan.
          </p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.id}
              className={`session-link ${s.id === activeId ? 'active' : ''}`}
              onClick={() => void selectSession(s.id)}
            >
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '190px' }}>
                {s.title}
              </span>
              <Icon name="chevron-right" size={14} style={{ opacity: s.id === activeId ? 1 : 0.4 }} />
            </button>
          ))
        )}
      </div>
    </div>
  )
}
