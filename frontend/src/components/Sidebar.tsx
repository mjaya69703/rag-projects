import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useSessions } from '../context/SessionsContext'
import { useCommandPalette } from '../context/CommandPaletteContext'
import { useHealthStatus, type HealthStatus } from '../hooks/useHealthStatus'
import { Icon } from './Icon'

const NAV = [
  { to: '/library', label: 'Library', icon: 'i-file' },
  { to: '/quiz', label: 'Quiz', icon: 'i-quiz' },
  { to: '/flashcards', label: 'Flashcards', icon: 'i-card' },
  { to: '/progress', label: 'Progress', icon: 'i-chart' },
  { to: '/settings', label: 'Settings', icon: 'i-theme' },
  { to: '/glossary', label: 'Glossary', icon: 'i-mark' },
]

/** Link navigasi utama — dipakai di sidebar semua halaman. */
export function NavLinks() {
  return (
    <nav className="side-section nav-section" aria-label="Navigasi halaman">
      {NAV.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}
        >
          <Icon name={item.icon} /> {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

const STATUS_LABEL: Record<HealthStatus, string> = {
  connecting: 'Menghubungkan…',
  connected: 'API terhubung',
  degraded: 'API menurun',
  offline: 'API offline',
}

const STATUS_CLASS: Record<HealthStatus, string> = {
  connecting: 'is-connecting',
  connected: 'is-ok',
  degraded: 'is-degraded',
  offline: 'is-error',
}

/** Indikator live status API — polling /health; klik untuk cek ulang manual. */
function HealthIndicator() {
  const { status, checkedAt, retry } = useHealthStatus()
  const lastChecked = checkedAt
    ? checkedAt.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '—'
  return (
    <button
      type="button"
      className={`status-line ${STATUS_CLASS[status]}`}
      onClick={() => void retry()}
      title={`Status API: ${STATUS_LABEL[status]} — dicek terakhir ${lastChecked}. Klik untuk cek ulang.`}
      aria-label={`Status API: ${STATUS_LABEL[status]}. Klik untuk cek ulang.`}
    >
      <span className="status-dot" />
      <span>{STATUS_LABEL[status]}</span>
      {status !== 'connected' && <Icon name="i-refresh" className="icon status-refresh" />}
    </button>
  )
}

/** Sidebar lengkap: brand + navigasi + sessions (chat) + perintah + status. */
export function Sidebar({ children }: { children?: React.ReactNode }) {
  const { createSession } = useSessions()
  const { openCommandPalette } = useCommandPalette()
  const [creating, setCreating] = useState(false)

  async function handleCreate() {
    if (creating) return
    setCreating(true)
    try {
      await createSession()
    } finally {
      setCreating(false)
    }
  }

  return (
    <aside className="sidebar" aria-label="Navigasi workspace">
      <div className="brand-row">
        <NavLink className="brand" to="/" aria-label="Knowledge Base beranda">
          <span className="brand-mark">
            <Icon name="i-mark" />
          </span>
          <span>
            Knowledge
            <br />
            Base
          </span>
        </NavLink>
      </div>

      <button className="new-chat" type="button" disabled={creating} onClick={() => void handleCreate()}>
        {creating ? <span className="spinner" style={{ marginRight: '0.4rem' }} /> : <Icon name="i-plus" />}
        <span>{creating ? 'Membuat Chat…' : 'Chat baru'}</span>
      </button>

      <NavLinks />

      {children}

      <div className="sidebar-bottom">
        <button className="command-button" type="button" title="Ctrl K" onClick={openCommandPalette}>
          <span>Perintah</span>
          <kbd>Ctrl K</kbd>
        </button>
        <HealthIndicator />
      </div>
    </aside>
  )
}

/** Section sessions (chat) untuk sidebar — dipakai di halaman chat. */
export function SessionsSection() {
  const { sessions, activeId, selectSession } = useSessions()
  return (
    <section className="side-section session-section" aria-labelledby="sessions-label">
      <div className="section-label-row">
        <h2 id="sessions-label">Percakapan</h2>
        <span className="badge">{sessions.length}</span>
      </div>
      <div className="session-list" aria-live="polite">
        {sessions.length === 0 && <p className="empty-list">Belum ada chat.</p>}
        {sessions.map((session) => (
          <button
            key={session.id}
            type="button"
            className={`session-button${session.id === activeId ? ' is-active' : ''}`}
            title={session.title}
            onClick={() => void selectSession(session.id)}
          >
            <span>{session.title}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
