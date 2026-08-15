import React, { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

export interface ToastItem {
  id: string
  message: string
  type: 'info' | 'success' | 'warning' | 'error'
}

interface ToastContextValue {
  toasts: ToastItem[]
  addToast: (message: string, type?: 'info' | 'success' | 'warning' | 'error', duration?: number) => void
  removeToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue>({
  toasts: [],
  addToast: () => {},
  removeToast: () => {},
})

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback((message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info', duration = 3500) => {
    const id = Math.random().toString(36).substring(2, 9)
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      removeToast(id)
    }, duration)
  }, [removeToast])

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      {/* Toast Notification Container */}
      <div
        style={{
          position: 'fixed',
          bottom: '1.5rem',
          right: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.5rem',
          zIndex: 9999,
          pointerEvents: 'none',
        }}
      >
        {toasts.map((t) => {
          const bg =
            t.type === 'success'
              ? 'var(--success)'
              : t.type === 'error'
              ? 'var(--error)'
              : t.type === 'warning'
              ? 'var(--warning)'
              : 'var(--accent)'

          return (
            <div
              key={t.id}
              style={{
                pointerEvents: 'auto',
                background: 'var(--bg-surface)',
                border: `1px solid var(--border-default)`,
                borderLeft: `4px solid ${bg}`,
                color: 'var(--text-primary)',
                padding: '0.75rem 1.25rem',
                borderRadius: 'var(--radius-md)',
                boxShadow: 'var(--shadow-lg)',
                fontSize: '0.85rem',
                fontWeight: '600',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
                animation: 'fadeIn 0.2s ease-out',
                maxWidth: '380px',
              }}
            >
              <span>{t.message}</span>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
