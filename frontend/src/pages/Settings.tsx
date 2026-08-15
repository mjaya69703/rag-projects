import { useEffect, useState } from 'react'
import { api, type PrivacyInfo } from '../api'
import { Icon } from '../components/Icon'
import { usePageHeader } from '../components/PageHeader'
import { useToast } from '../components/Toast'

interface Metrics {
  cache_hits: number
  cache_misses: number
  queries: number
  llm_errors: number
}

/** Halaman /settings — Control Panel System & Integrasi Eksternal. */
export default function Settings() {
  const toast = useToast()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [health, setHealth] = useState<string>('')
  const [docCount, setDocCount] = useState<number | null>(null)
  const [privacy, setPrivacy] = useState<PrivacyInfo | null>(null)
  const [theme, setTheme] = useState(() => (localStorage.getItem('kb-theme') === 'light' ? 'light' : 'dark'))

  usePageHeader({ eyebrow: 'KONFIGURASI & SISTEM', title: 'Settings & Metrics' })

  useEffect(() => {
    void (async () => {
      try {
        const [m, h, d] = await Promise.all([
          api<Metrics>('/metrics'),
          api<{ status: string }>('/health'),
          api<{ documents: unknown[] }>('/documents'),
        ])
        setMetrics(m)
        setHealth(h.status)
        setDocCount(d.documents.length)
      } catch (error) {
        toast(error instanceof Error ? error.message : 'Gagal memuat info sistem.')
      }
    })()
  }, [toast])

  // Info privasi dipisah agar kegagalan /privacy/info tidak mengganggu metrik lain.
  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 4000)
    void (async () => {
      try {
        const res = await fetch('/privacy/info', { signal: controller.signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        setPrivacy((await res.json()) as PrivacyInfo)
      } catch {
        setPrivacy(null)
      } finally {
        clearTimeout(timer)
      }
    })()
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [])

  function toggleTheme() {
    const next = theme === 'light' ? 'dark' : 'light'
    setTheme(next)
    document.documentElement.dataset.theme = next === 'light' ? 'light' : ''
    localStorage.setItem('kb-theme', next)
    toast(`Tema diubah ke mode ${next === 'light' ? 'Terang' : 'Gelap'}.`)
  }

  function copyToClipboard(text: string, label: string) {
    void navigator.clipboard.writeText(text)
    toast(`${label} disalin ke clipboard! 📋`)
  }

  const total = metrics ? metrics.cache_hits + metrics.cache_misses : 0
  const hitRate = total > 0 ? Math.round((metrics!.cache_hits / total) * 100) : 0

  return (
    <div className="page-content">
      <div className="library-grid">
        {/* Card Tampilan & Tema */}
        <section className="library-card" aria-labelledby="set-theme-label">
          <div className="section-label-row">
            <h2 id="set-theme-label">🎨 Tema Tampilan</h2>
            <span className="badge">{theme.toUpperCase()} MODE</span>
          </div>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginBottom: 'var(--space-3)' }}>
            Pilih tema antarmuka sesuai kenyamanan Anda saat membaca materi.
          </p>
          <button
            className="button button-secondary"
            type="button"
            onClick={toggleTheme}
            style={{ width: '100%', justifyContent: 'center' }}
          >
            <Icon name="i-theme" /> Switch ke Mode {theme === 'light' ? 'Gelap (Dark Slate)' : 'Terang (Light)'}
          </button>
        </section>

        {/* Card Status & Kesehatan Sistem */}
        <section className="library-card" aria-labelledby="set-sys-label">
          <div className="section-label-row">
            <h2 id="set-sys-label">⚡ Status & Metrik Performa</h2>
            <span className="badge">LIVE METRICS</span>
          </div>

          <div className="repeated-item" style={{ padding: '0.5rem 0.75rem' }}>
            <span className="repeated-question">Status API Backend</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span className="status-dot" style={{ background: health === 'ok' ? 'var(--color-success)' : 'var(--color-error)' }} />
              <small style={{ fontWeight: 700, color: health === 'ok' ? 'var(--color-success)' : 'var(--color-error)' }}>
                {health ? health.toUpperCase() : 'MEMUAT…'}
              </small>
            </div>
          </div>

          <div className="repeated-item" style={{ padding: '0.5rem 0.75rem' }}>
            <span className="repeated-question">Dokumen Terindeks</span>
            <small style={{ fontWeight: 700, color: 'var(--color-ink)' }}>{docCount ?? '…'} dokumen</small>
          </div>

          <div className="repeated-item" style={{ padding: '0.5rem 0.75rem' }}>
            <span className="repeated-question">Total Query RAG</span>
            <small style={{ fontWeight: 700, color: 'var(--color-ink)' }}>{metrics?.queries ?? '…'} kali</small>
          </div>

          {/* Cache Hit Rate Meter */}
          <div style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', background: 'var(--color-paper-soft)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem' }}>
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 600 }}>Semantic Cache Hit Rate</span>
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, color: 'var(--color-accent)' }}>
                {total ? `${hitRate}% (${metrics!.cache_hits}/${total})` : '0%'}
              </span>
            </div>
            <div className="progress-track" style={{ height: '0.4rem' }}>
              <div className="progress-fill" style={{ width: `${hitRate}%` }} />
            </div>
          </div>

          <div className="repeated-item" style={{ padding: '0.5rem 0.75rem', marginTop: 'var(--space-2)' }}>
            <span className="repeated-question">Error LLM Client</span>
            <small style={{ fontWeight: 700, color: metrics?.llm_errors ? 'var(--color-error)' : 'var(--color-success)' }}>
              {metrics?.llm_errors ?? 0} error
            </small>
          </div>
        </section>

        {/* Card Akses & Integrasi Eksternal */}
        <section className="library-card" aria-labelledby="set-access-label" style={{ gridColumn: 'span 2' }}>
          <div className="section-label-row">
            <h2 id="set-access-label">🔌 Integrasi MCP Server & Bot Telegram</h2>
            <span className="badge">INTEGRATION HUB</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(20rem, 1fr))', gap: 'var(--space-4)', marginTop: 'var(--space-2)' }}>
            {/* MCP Server Box */}
            <div style={{ padding: 'var(--space-4)', border: '1px solid var(--color-rule)', borderRadius: 'var(--radius-md)', background: 'var(--color-paper-raised)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                <Icon name="i-zap" />
                <strong style={{ fontSize: 'var(--text-sm)' }}>Model Context Protocol (MCP) Server</strong>
              </div>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginBottom: 'var(--space-3)' }}>
                Hubungkan Knowledge Base ini dengan Claude Desktop atau tool AI lainnya via standar MCP protocol.
              </p>
              <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                <code style={{ flex: 1, padding: '0.4rem 0.6rem', background: 'var(--color-paper)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                  .venv\Scripts\python -m app.mcp_server
                </code>
                <button
                  className="button button-secondary"
                  style={{ minHeight: '32px', padding: '0 0.6rem', fontSize: '0.7rem' }}
                  onClick={() => copyToClipboard('.venv\\Scripts\\python -m app.mcp_server', 'Perintah MCP Server')}
                >
                  Salin
                </button>
              </div>
            </div>

            {/* Telegram Bot Box */}
            <div style={{ padding: 'var(--space-4)', border: '1px solid var(--color-rule)', borderRadius: 'var(--radius-md)', background: 'var(--color-paper-raised)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
                <Icon name="i-chat" />
                <strong style={{ fontSize: 'var(--text-sm)' }}>Bot Telegram Knowledge Base</strong>
              </div>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginBottom: 'var(--space-3)' }}>
                Jalankan bot Telegram untuk berinteraksi dengan RAG langsung dari pesan singkat (butuh <code>TELEGRAM_BOT_TOKEN</code> di file <code>.env</code>).
              </p>
              <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                <code style={{ flex: 1, padding: '0.4rem 0.6rem', background: 'var(--color-paper)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                  .venv\Scripts\python -m app.telegram_bot
                </code>
                <button
                  className="button button-secondary"
                  style={{ minHeight: '32px', padding: '0 0.6rem', fontSize: '0.7rem' }}
                  onClick={() => copyToClipboard('.venv\\Scripts\\python -m app.telegram_bot', 'Perintah Bot Telegram')}
                >
                  Salin
                </button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
