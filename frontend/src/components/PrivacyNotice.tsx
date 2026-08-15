import { useEffect, useState } from 'react'
import type { PrivacyInfo } from '../api'
import { Dialog, DialogHeading } from './Dialog'

const ACK_KEY = 'privacy_ack_v1'
const FETCH_TIMEOUT_MS = 4_000

const FALLBACK_DISCLOSURE =
  'Aplikasi ini memproses dokumen dan pertanyaan Anda untuk keperluan RAG. Dokumen yang diunggah menjadi basis pengetahuan lokal Anda dan dipakai hanya untuk menjawab pertanyaan. Data tidak dibagikan ke pihak ketiga, kecuali saat fitur yang memakai layanan LLM eksternal diaktifkan — detailnya dijelaskan di halaman Settings.'

/**
 * Pemberitahuan privasi sekali-muat: muncul saat app pertama kali dibuka,
 * teks diambil dari GET /privacy/info (fallback statis jika backend offline),
 * dan tidak muncul lagi setelah dikonfirmasi (persist di localStorage).
 */
export function PrivacyNotice() {
  const [info, setInfo] = useState<PrivacyInfo | null>(null)
  const [ready, setReady] = useState(false)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (localStorage.getItem(ACK_KEY)) return
    let cancelled = false
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
    void (async () => {
      try {
        const res = await fetch('/privacy/info', { signal: controller.signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = (await res.json()) as PrivacyInfo
        if (!cancelled && data && typeof data.disclosure_text === 'string' && data.disclosure_text.trim()) {
          setInfo(data)
        }
      } catch {
        // Backend offline / endpoint belum tersedia → pakai fallback statis.
      } finally {
        clearTimeout(timer)
        if (!cancelled) {
          setReady(true)
          setOpen(true)
        }
      }
    })()
    return () => {
      cancelled = true
      clearTimeout(timer)
      controller.abort()
    }
  }, [])

  if (!ready) return null

  function acknowledge() {
    localStorage.setItem(ACK_KEY, '1')
    setOpen(false)
  }

  return (
    <Dialog open={open} onClose={acknowledge}>
      <div className="modal-card privacy-notice">
        <DialogHeading eyebrow="PRIVASI & DATA" title="Pemberitahuan Privasi" onClose={acknowledge} />
        <p className="privacy-body">{info?.disclosure_text || FALLBACK_DISCLOSURE}</p>
        {info ? (
          <>
            <div className="privacy-facts">
              <div className="privacy-fact">
                <strong>PENYEDIA AI</strong>
                <span>{info.provider_label || '—'}</span>
              </div>
              <div className="privacy-fact">
                <strong>REDAKSI SENSITIF</strong>
                <span>{info.redaction_enabled ? 'Aktif' : 'Nonaktif'}</span>
              </div>
              <div className="privacy-fact">
                <strong>RETENSI DATA</strong>
                <span>{info.retention_days ? `${info.retention_days} hari` : '—'}</span>
              </div>
            </div>
            {info.external_data_flow ? <p className="privacy-flow">{info.external_data_flow}</p> : null}
          </>
        ) : null}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 'var(--space-4)' }}>
          <button className="button button-primary" type="button" onClick={acknowledge}>
            Saya Mengerti
          </button>
        </div>
      </div>
    </Dialog>
  )
}
