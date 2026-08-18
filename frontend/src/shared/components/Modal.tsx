import React, { useEffect, useRef } from 'react'
import { Icon } from './Icon'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: React.ReactNode
  subtitle?: string
  children: React.ReactNode
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl'
  footer?: React.ReactNode
}

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  maxWidth = 'md',
  footer,
}) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const previouslyFocusedRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!isOpen) return

    previouslyFocusedRef.current = document.activeElement as HTMLElement | null

    const container = containerRef.current
    if (container) {
      const focusable = container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      if (focusable.length > 0) {
        focusable[0].focus()
      } else {
        container.focus()
      }
    }

    return () => {
      previouslyFocusedRef.current?.focus?.()
      previouslyFocusedRef.current = null
    }
  }, [isOpen])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        e.stopPropagation()
        onClose()
        return
      }

      if (e.key !== 'Tab' || !isOpen) return
      const container = containerRef.current
      if (!container) return

      const focusable = Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR))
      if (focusable.length === 0) {
        e.preventDefault()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        ref={containerRef}
        className={`modal-container modal--${maxWidth}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={typeof title === 'string' ? title : undefined}
        tabIndex={-1}
      >
        {title && (
          <div className="modal-header">
            <div>
              <h3 className="modal-title">{title}</h3>
              {subtitle && <p className="modal-subtitle">{subtitle}</p>}
            </div>
            <button className="modal-close-btn" onClick={onClose} aria-label="Tutup">
              <Icon name="x" size={18} />
            </button>
          </div>
        )}
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  )
}
