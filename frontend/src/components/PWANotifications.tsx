import React from 'react'
import { usePWA } from '../context/PWAContext'
import { Button, Icon, Modal } from '../shared/components'

export function PWANotifications() {
  const {
    isOffline,
    swUpdateAvailable,
    applyUpdate,
    showInstallGuide,
    setShowInstallGuide,
  } = usePWA()

  return (
    <>
      {/* Offline Status Alert */}
      {isOffline && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            zIndex: 9999,
            background: 'linear-gradient(90deg, #dc2626 0%, #b91c1c 100%)',
            color: '#ffffff',
            padding: '0.4rem 1rem',
            textAlign: 'center',
            fontSize: '0.8rem',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.5rem',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.3)',
          }}
        >
          <Icon name="alert" size={16} />
          <span>Anda sedang offline. Menampilkan antarmuka statis tersimpan (PWA cache).</span>
        </div>
      )}

      {/* SW Update Available Banner */}
      {swUpdateAvailable && (
        <div
          style={{
            position: 'fixed',
            bottom: '4.5rem',
            left: '50%',
            transform: 'translateX(-50%)',
            zIndex: 9998,
            background: 'var(--bg-surface-floating)',
            backdropFilter: 'var(--glass-blur)',
            WebkitBackdropFilter: 'var(--glass-blur)',
            border: '1px solid var(--accent)',
            borderRadius: 'var(--radius-lg)',
            padding: '0.75rem 1.25rem',
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
            boxShadow: 'var(--shadow-lg)',
            animation: 'scaleIn 0.2s ease-out',
            maxWidth: '90vw',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent)' }}>
            <Icon name="sparkles" size={20} />
            <span style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-primary)' }}>
              Pembaruan Cortex AI tersedia!
            </span>
          </div>
          <Button variant="primary" size="sm" onClick={applyUpdate}>
            Perbarui
          </Button>
        </div>
      )}

      {/* iOS Install Guide Modal */}
      <Modal
        isOpen={showInstallGuide}
        onClose={() => setShowInstallGuide(false)}
        title="Pasang Cortex AI di iPhone / iPad"
        subtitle="Instal aplikasi ke Home Screen untuk pengalaman layar penuh terbaik."
        footer={
          <Button variant="primary" onClick={() => setShowInstallGuide(false)}>
            Mengerti
          </Button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: 'var(--accent-bg)',
                color: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                flexShrink: 0,
              }}
            >
              1
            </div>
            <div>
              Buka website ini di browser <strong>Safari</strong> pada iPhone/iPad Anda.
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: 'var(--accent-bg)',
                color: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                flexShrink: 0,
              }}
            >
              2
            </div>
            <div>
              Ketuk tombol <strong>Share / Bagikan</strong> di bilah navigasi bawah Safari (ikon kotak dengan panah ke atas).
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                background: 'var(--accent-bg)',
                color: 'var(--accent)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                flexShrink: 0,
              }}
            >
              3
            </div>
            <div>
              Gulir menu ke bawah lalu pilih <strong>Add to Home Screen (Tambah ke Layar Utama)</strong>.
            </div>
          </div>
        </div>
      </Modal>
    </>
  )
}
