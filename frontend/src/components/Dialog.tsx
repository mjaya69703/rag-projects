import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  children: ReactNode
}

/** Dialog native <dialog> yang di-control lewat prop open/onClose. */
export function Dialog({ open, onClose, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    else if (!open && dialog.open) dialog.close()
  }, [open])

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    const onCancel = (event: Event) => {
      event.preventDefault()
      onClose()
    }
    dialog.addEventListener('cancel', onCancel)
    return () => dialog.removeEventListener('cancel', onCancel)
  }, [onClose])

  return (
    <dialog ref={ref} className="modal">
      {children}
    </dialog>
  )
}

/** Heading dialog + tombol tutup — pola konsisten semua dialog. */
export function DialogHeading({ eyebrow, title, onClose }: { eyebrow?: string; title: string; onClose: () => void }) {
  return (
    <div className="modal-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
      </div>
      <button className="icon-button" aria-label="Tutup" onClick={onClose}>
        <svg className="icon" aria-hidden="true">
          <use href="#i-close" />
        </svg>
      </button>
    </div>
  )
}
