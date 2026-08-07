import { useEffect, useState, type FormEvent } from 'react'
import { Dialog, DialogHeading } from './Dialog'

interface PromptDialogProps {
  open: boolean
  title: string
  message?: string
  defaultValue?: string
  placeholder?: string
  confirmText?: string
  cancelText?: string
  multiline?: boolean
  loading?: boolean
  onConfirm: (value: string) => void
  onClose: () => void
}

/** Modal prompt input teks kustom menggantikan prompt() bawaan browser. */
export function PromptDialog({
  open,
  title,
  message,
  defaultValue = '',
  placeholder = 'Ketik di sini…',
  confirmText = 'Simpan',
  cancelText = 'Batal',
  multiline = false,
  loading = false,
  onConfirm,
  onClose,
}: PromptDialogProps) {
  const [value, setValue] = useState(defaultValue)

  useEffect(() => {
    if (open) setValue(defaultValue)
  }, [open, defaultValue])

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    onConfirm(value)
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <div className="modal-card">
        <DialogHeading eyebrow="INPUT TEKS" title={title} onClose={onClose} />
        <form onSubmit={handleSubmit}>
          {message && (
            <p style={{ margin: 'var(--space-2) 0 var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>
              {message}
            </p>
          )}

          <div style={{ margin: 'var(--space-3) 0 var(--space-4)' }}>
            {multiline ? (
              <textarea
                className="chunk-search"
                style={{ width: '100%', minHeight: '80px', resize: 'vertical' }}
                placeholder={placeholder}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                autoFocus
              />
            ) : (
              <input
                type="text"
                className="chunk-search"
                style={{ width: '100%' }}
                placeholder={placeholder}
                value={value}
                onChange={(e) => setValue(e.target.value)}
                autoFocus
              />
            )}
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end' }}>
            <button className="button button-secondary" type="button" disabled={loading} onClick={onClose}>
              {cancelText}
            </button>
            <button className="button button-primary" type="submit" disabled={loading}>
              {loading ? <span className="spinner" style={{ marginRight: '0.3rem' }} /> : null}
              <span>{loading ? 'Menyimpan…' : confirmText}</span>
            </button>
          </div>
        </form>
      </div>
    </Dialog>
  )
}
