import { Dialog, DialogHeading } from './Dialog'

interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  loading?: boolean
  onConfirm: () => void
  onClose: () => void
}

/** Modal konfirmasi kustom menggantikan confirm() bawaan browser. */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmText = 'Konfirmasi',
  cancelText = 'Batal',
  danger = false,
  loading = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Dialog open={open} onClose={onClose}>
      <div className="modal-card">
        <DialogHeading eyebrow={danger ? 'KONFIRMASI BAHAYA' : 'KONFIRMASI'} title={title} onClose={onClose} />
        <p style={{ margin: 'var(--space-3) 0 var(--space-5)', fontSize: 'var(--text-sm)', color: 'var(--color-ink)', lineHeight: 1.6 }}>
          {message}
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
          <button className="button button-secondary" type="button" disabled={loading} onClick={onClose}>
            {cancelText}
          </button>
          <button
            className={`button ${danger ? '' : 'button-primary'}`}
            type="button"
            disabled={loading}
            onClick={onConfirm}
            style={
              danger
                ? {
                    background: 'var(--color-error-bg)',
                    color: 'var(--color-error)',
                    border: '1px solid var(--color-error)',
                  }
                : undefined
            }
          >
            {loading ? <span className="spinner" style={{ marginRight: '0.3rem' }} /> : null}
            <span>{loading ? 'Memproses…' : confirmText}</span>
          </button>
        </div>
      </div>
    </Dialog>
  )
}
