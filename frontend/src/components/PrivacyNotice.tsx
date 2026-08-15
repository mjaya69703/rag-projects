import React, { useEffect, useState } from 'react'
import { Badge, Button, Icon, Modal } from '../shared/components'
import type { PrivacyInfo } from '../shared/types'

const ACK_KEY = 'privacy_ack_v2'

export function PrivacyNotice() {
  const [info, setInfo] = useState<PrivacyInfo | null>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (localStorage.getItem(ACK_KEY)) return

    void (async () => {
      try {
        const res = await fetch('/privacy/info')
        if (res.ok) {
          const data = (await res.json()) as PrivacyInfo
          setInfo(data)
        }
      } catch {
        // ignore
      } finally {
        setOpen(true)
      }
    })()
  }, [])

  const handleAcknowledge = () => {
    localStorage.setItem(ACK_KEY, '1')
    setOpen(false)
  }

  if (!open) return null

  return (
    <Modal
      isOpen={open}
      onClose={handleAcknowledge}
      title="Pemberitahuan Privasi & Alur Data"
      subtitle="Transparansi pemrosesan dokumen dan interaksi model AI lokal/eksternal."
      size="md"
      footer={
        <Button variant="primary" icon="check" onClick={handleAcknowledge}>
          Saya Mengerti & Setuju
        </Button>
      }
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
          {info?.disclosure_text ||
            'Aplikasi ini memproses dokumen dan pertanyaan Anda untuk keperluan RAG. Seluruh dokumen tersimpan secara lokal dalam database dan vector store di mesin Anda.'}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
          <div style={{ padding: '0.75rem', background: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              LLM Provider
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: '700', color: 'var(--text-primary)', marginTop: '0.2rem' }}>
              {info?.provider_label || 'Lokal / External'}
            </div>
          </div>

          <div style={{ padding: '0.75rem', background: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Sensor PII
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: '700', color: info?.redaction_active ? 'var(--success)' : 'var(--warning)', marginTop: '0.2rem' }}>
              {info?.redaction_active ? '🛡️ Aktif' : '⚠️ Nonaktif'}
            </div>
          </div>

          <div style={{ padding: '0.75rem', background: 'var(--bg-surface-raised)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <div style={{ fontSize: '0.72rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Retensi Chat
            </div>
            <div style={{ fontSize: '0.88rem', fontWeight: '700', color: 'var(--text-primary)', marginTop: '0.2rem' }}>
              {info?.retention_days ? `${info.retention_days} Hari` : 'Tanpa Batas'}
            </div>
          </div>
        </div>
      </div>
    </Modal>
  )
}
