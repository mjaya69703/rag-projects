import React, { useEffect, useState } from 'react'
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  Icon,
  Input,
  PageHeader,
  Spinner,
  StatCard,
} from '../shared/components'
import { usePWA } from '../context/PWAContext'
import { useTheme, useToast } from '../shared/hooks'
import { learningService, systemService } from '../shared/services'
import type { PrivacyInfo } from '../shared/types'

export default function Settings() {
  const { theme, toggleTheme, isDark } = useTheme()
  const { addToast } = useToast()
  const { isInstallable, isInstalled, isIOS, promptInstall } = usePWA()
  const [privacyInfo, setPrivacyInfo] = useState<PrivacyInfo | null>(null)
  const [loading, setLoading] = useState(true)

  // API Token
  const [token, setToken] = useState(() => localStorage.getItem('kb_api_token') || '')

  // Purge Dialogs
  const [isWipeDialogOpen, setIsWipeDialogOpen] = useState(false)
  const [isCacheDialogOpen, setIsCacheDialogOpen] = useState(false)
  const [purging, setPurging] = useState(false)

  useEffect(() => {
    loadPrivacyInfo()
  }, [])

  const loadPrivacyInfo = async () => {
    setLoading(true)
    try {
      const res = await systemService.getPrivacyInfo()
      setPrivacyInfo(res)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }

  const handleSaveToken = () => {
    localStorage.setItem('kb_api_token', token.trim())
    addToast('Bearer API Token berhasil disimpan!', 'success')
  }

  const handleWipeUserData = async () => {
    setPurging(true)
    try {
      const res = await systemService.clearUserData()
      addToast('Seluruh data pribadi (termasuk dokumen) berhasil dihapus!', 'success')
      setIsWipeDialogOpen(false)
    } catch (err: any) {
      addToast(err.message || 'Gagal menghapus data pribadi.', 'error')
    } finally {
      setPurging(false)
    }
  }

  const handleClearCache = async () => {
    setPurging(true)
    try {
      const res = await systemService.clearSemanticCache()
      addToast(`Semantic cache dibersihkan (${res.cleared_entries} entri)!`, 'success')
      setIsCacheDialogOpen(false)
    } catch (err: any) {
      addToast(err.message || 'Gagal membersihkan cache.', 'error')
    } finally {
      setPurging(false)
    }
  }

  const handleExportData = async () => {
    setPurging(true)
    try {
      const res = await learningService.exportLearningData()
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `learning_backup_${new Date().toISOString().substring(0, 10)}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      addToast('Data belajar berhasil diunduh sebagai backup!', 'success')
    } catch (err: any) {
      addToast(err.message || 'Gagal mengekspor data belajar.', 'error')
    } finally {
      setPurging(false)
    }
  }

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <PageHeader
        title="Pengaturan & Preferensi"
        subtitle="Kelola tema antarmuka, aplikasi PWA, keamanan token otentikasi, privasi data PII, dan cache semantic."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: '1.25rem' }}>
        {/* PWA & Mobile App Card */}
        <Card padding="lg">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', background: 'var(--accent-bg)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="sparkles" size={20} />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--text-primary)' }}>Progressive Web App (PWA)</h3>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem', lineHeight: '1.6' }}>
            Jadikan Cortex AI aplikasi mandiri di perangkat Anda dengan navigasi layar penuh dan dukungan offline cache.
          </p>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface-raised)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-md)', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <div style={{ fontSize: '0.88rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                {isInstalled ? '✅ Terpasang di Perangkat' : '📱 Siap Dipasang'}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {isInstalled ? 'Mode Standalone Aktif' : isIOS ? 'Mendukung iOS Home Screen' : 'Mendukung Android & Desktop PWA'}
              </div>
            </div>
            {!isInstalled && (
              <Button
                variant="primary"
                size="sm"
                icon="download"
                onClick={() => void promptInstall()}
              >
                Pasang Aplikasi
              </Button>
            )}
          </div>
        </Card>

        {/* Appearance Card */}
        <Card padding="lg">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', background: 'var(--accent-bg)', color: 'var(--accent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name={isDark ? 'moon' : 'sun'} size={20} />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--text-primary)' }}>Tampilan & Tema</h3>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1.25rem', lineHeight: '1.6' }}>
            Sesuaikan palet visual antara Cyber Dark Mode dan Frost Light Mode.
          </p>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface-raised)', padding: '0.85rem 1rem', borderRadius: 'var(--radius-md)', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <div style={{ fontSize: '0.88rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                {isDark ? '🌙 Dark Cyber Slate' : '☀️ Light Frost Glass'}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>OKLCH High-Contrast</div>
            </div>
            <Button variant="secondary" size="sm" icon={isDark ? 'sun' : 'moon'} onClick={toggleTheme}>
              Beralih ke {isDark ? 'Light' : 'Dark'}
            </Button>
          </div>
        </Card>

        {/* API Token Security */}
        <Card padding="lg">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', background: 'var(--cyan-bg)', color: 'var(--cyan)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Icon name="shield" size={20} />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--text-primary)' }}>API Authentication Token</h3>
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem', lineHeight: '1.6' }}>
            Masukkan Bearer token rahasia bila backend diproteksi dengan <code>AUTH_API_TOKEN</code>.
          </p>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 180px' }}>
              <Input
                type="password"
                placeholder="Bearer token otentikasi..."
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
            </div>
            <Button variant="primary" icon="check" size="md" onClick={handleSaveToken}>
              Simpan
            </Button>
          </div>
        </Card>
      </div>

      {/* Privacy & Data Flow Information */}
      <Card padding="lg">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', background: 'var(--success-bg)', color: 'var(--success)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="shield" size={20} />
          </div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-primary)' }}>Keterbukaan Alur Data & Privasi</h3>
        </div>

        {loading ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <Spinner size="md" text="Memuat informasi privasi..." />
          </div>
        ) : (
          <div>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.65', marginBottom: '1.5rem' }}>
              {privacyInfo?.disclosure_text}
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ padding: '1rem 1.15rem', background: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>LLM Provider</div>
                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                  {privacyInfo?.provider_label}
                </div>
              </div>

              <div style={{ padding: '1rem 1.15rem', background: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Sensor PII Otomatis</div>
                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: privacyInfo?.redaction_active ? 'var(--success)' : 'var(--warning)', marginTop: '0.25rem' }}>
                  {privacyInfo?.redaction_active ? '🛡️ Aktif (Sensitif Disensor)' : '⚠️ Nonaktif'}
                </div>
              </div>

              <div style={{ padding: '1rem 1.15rem', background: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Retensi Sesi Chat</div>
                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                  {privacyInfo?.retention_days ? `${privacyInfo.retention_days} Hari` : 'Tanpa Batas'}
                </div>
              </div>

              <div style={{ padding: '1rem 1.15rem', background: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-muted)' }}>TTL Semantic Cache</div>
                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: 'var(--text-primary)', marginTop: '0.25rem' }}>
                  {privacyInfo?.cache_max_days ? `${privacyInfo.cache_max_days} Hari` : 'Tanpa Batas'}
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Maintenance & Danger Zone */}
      <Card padding="lg" style={{ border: '1px solid oklch(from var(--error) l c h / 0.35)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', background: 'var(--error-bg)', color: 'var(--error)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Icon name="trash" size={20} />
          </div>
          <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--error)' }}>Zona Pemeliharaan & Data Wipe</h3>
        </div>

        <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', lineHeight: '1.6' }}>
          Unduh cadangan data belajar Anda (deck flashcard, riwayat kuis, glossary, progres) atau bersihkan cache jawaban / hapus jejak riwayat aktivitas pembelajaran secara permanen.
        </p>

        <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap' }}>
          <Button
            variant="secondary"
            icon="download"
            onClick={handleExportData}
            loading={purging}
          >
            Unduh Data Belajar (Backup)
          </Button>
          <Button
            variant="secondary"
            icon="refresh"
            onClick={() => setIsCacheDialogOpen(true)}
            disabled={purging}
          >
            Bersihkan Semantic Cache
          </Button>
          <Button
            variant="danger"
            icon="trash"
            onClick={() => setIsWipeDialogOpen(true)}
            disabled={purging}
          >
            Hapus Semua Riwayat Data Pribadi
          </Button>
        </div>
      </Card>

      {/* Wipe User Data Dialog */}
      <ConfirmDialog
        isOpen={isWipeDialogOpen}
        title="Hapus Semua Data Pribadi?"
        description="Aksi ini akan menghapus SEMUA data Anda secara permanen: percakapan, riwayat kuis, kartu flashcards, catatan, glossary, dan seluruh dokumen yang terindeks (perpustakaan ikut dikosongkan)."
        confirmText="Hapus Seluruh Data"
        loading={purging}
        onConfirm={handleWipeUserData}
        onCancel={() => setIsWipeDialogOpen(false)}
      />

      {/* Clear Cache Dialog */}
      <ConfirmDialog
        isOpen={isCacheDialogOpen}
        title="Bersihkan Semantic Cache?"
        description="Semua cache query jawaban instan akan dikosongkan. Pertanyaan berikutnya akan diproses ulang melalui LLM."
        confirmText="Kosongkan Cache"
        loading={purging}
        onConfirm={handleClearCache}
        onCancel={() => setIsCacheDialogOpen(false)}
      />
    </div>
  )
}
