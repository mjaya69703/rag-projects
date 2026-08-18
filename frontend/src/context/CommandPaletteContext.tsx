import React, { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Badge, Icon, type IconName } from '../shared/components'
import { useSessions } from './SessionsContext'

interface CommandPaletteValue {
  openCommandPalette: () => void
  closeCommandPalette: () => void
}

const CommandPaletteContext = createContext<CommandPaletteValue | null>(null)

export function useCommandPalette() {
  const ctx = useContext(CommandPaletteContext)
  if (!ctx) throw new Error('useCommandPalette harus dipakai di dalam CommandPaletteProvider')
  return ctx
}

interface CommandItem {
  id: string
  title: string
  subtitle?: string
  icon: IconName
  category: 'Aksi Cepat' | 'Navigasi Halaman'
  action: () => void
}

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { createSession } = useSessions()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const openCommandPalette = useCallback(() => {
    setQuery('')
    setSelectedIndex(0)
    setOpen(true)
  }, [])

  const closeCommandPalette = useCallback(() => {
    setOpen(false)
  }, [])

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [open])

  // Global shortcut (Ctrl+K or Cmd+K)
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((prev) => !prev)
      }
      if (event.key === 'Escape' && open) {
        setOpen(false)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const commands: CommandItem[] = [
    {
      id: 'new-chat',
      title: 'Chat Baru',
      subtitle: 'Mulai sesi percakapan baru dengan Cortex AI',
      icon: 'plus',
      category: 'Aksi Cepat',
      action: () => {
        createSession()
        navigate('/')
        setOpen(false)
      },
    },
    {
      id: 'upload-doc',
      title: 'Unggah Dokumen',
      subtitle: 'Buka Knowledge Library untuk mengunggah materi',
      icon: 'upload',
      category: 'Aksi Cepat',
      action: () => {
        navigate('/library')
        setOpen(false)
      },
    },
    {
      id: 'nav-chat',
      title: 'Chat Studio',
      subtitle: 'Tanya jawab interaktif berbasis dokumen RAG',
      icon: 'chat',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/')
        setOpen(false)
      },
    },
    {
      id: 'nav-library',
      title: 'Knowledge Library',
      subtitle: 'Kelola repositori dokumen dan berkas terindeks',
      icon: 'library',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/library')
        setOpen(false)
      },
    },
    {
      id: 'nav-cards',
      title: '3D Flashcards',
      subtitle: 'Latihan mengingat dengan spaced repetition SM-2',
      icon: 'cards',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/flashcards')
        setOpen(false)
      },
    },
    {
      id: 'nav-quiz',
      title: 'AI Quiz Arena',
      subtitle: 'Uji pemahaman dengan kuis pilihan ganda otomatis',
      icon: 'quiz',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/quiz')
        setOpen(false)
      },
    },
    {
      id: 'nav-glossary',
      title: 'Glosarium Istilah',
      subtitle: 'Kamus konsep kunci dan ekstraksi istilah AI',
      icon: 'glossary',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/glossary')
        setOpen(false)
      },
    },
    {
      id: 'nav-progress',
      title: 'Diagnostik & Progress',
      subtitle: 'Analisis titik lemah materi dan metrik sistem',
      icon: 'progress',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/progress')
        setOpen(false)
      },
    },
    {
      id: 'nav-annotations',
      title: 'Catatan Anotasi',
      subtitle: 'Catatan pribadi pada chunk dokumen',
      icon: 'note',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/annotations')
        setOpen(false)
      },
    },
    {
      id: 'nav-settings',
      title: 'Pengaturan & Privasi',
      subtitle: 'Konfigurasi tema, API token, dan data wipe',
      icon: 'settings',
      category: 'Navigasi Halaman',
      action: () => {
        navigate('/settings')
        setOpen(false)
      },
    },
  ]

  const filtered = commands.filter((c) =>
    c.title.toLowerCase().includes(query.toLowerCase()) ||
    (c.subtitle && c.subtitle.toLowerCase().includes(query.toLowerCase()))
  )

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filtered.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex((prev) => (prev - 1 + filtered.length) % Math.max(1, filtered.length))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (filtered[selectedIndex]) {
        filtered[selectedIndex].action()
      }
    }
  }

  return (
    <CommandPaletteContext.Provider value={{ openCommandPalette, closeCommandPalette }}>
      {children}

      {open && (
        <div
          className="modal-backdrop"
          onClick={closeCommandPalette}
          style={{ alignItems: 'flex-start', paddingTop: '12vh' }}
        >
          <div
            className="modal-container"
            onClick={(e) => e.stopPropagation()}
            style={{
              maxWidth: '580px',
              borderRadius: 'var(--radius-xl)',
              background: 'var(--bg-surface)',
              border: '1px solid var(--border-default)',
              boxShadow: 'var(--shadow-lg)',
              overflow: 'hidden',
            }}
          >
            {/* Search Input Bar */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '1rem 1.25rem',
                borderBottom: '1px solid var(--border-subtle)',
              }}
            >
              <Icon name="search" size={20} style={{ color: 'var(--text-muted)' }} />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setSelectedIndex(0)
                }}
                onKeyDown={handleKeyDown}
                placeholder="Ketik perintah atau navigasi halaman..."
                style={{
                  flex: 1,
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  fontSize: '0.95rem',
                  color: 'var(--text-primary)',
                }}
              />
              <Badge variant="neutral" size="sm">ESC</Badge>
            </div>

            {/* Command List */}
            <div style={{ maxHeight: '360px', overflowY: 'auto', padding: '0.5rem' }}>
              {filtered.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  Tidak ada perintah yang sesuai.
                </div>
              ) : (
                filtered.map((item, idx) => {
                  const isSelected = idx === selectedIndex
                  return (
                    <button
                      key={item.id}
                      onClick={item.action}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.75rem 1rem',
                        borderRadius: 'var(--radius-md)',
                        background: isSelected ? 'var(--accent-bg)' : 'transparent',
                        color: isSelected ? 'var(--accent)' : 'var(--text-primary)',
                        textAlign: 'left',
                        transition: 'background var(--dur-fast)',
                        border: 'none',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
                        <div
                          style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: 'var(--radius-sm)',
                            background: isSelected ? 'var(--accent)' : 'var(--bg-surface-raised)',
                            color: isSelected ? '#fff' : 'var(--text-secondary)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            transition: 'all var(--dur-fast)',
                          }}
                        >
                          <Icon name={item.icon} size={16} />
                        </div>
                        <div>
                          <div style={{ fontWeight: '600', fontSize: '0.88rem', color: isSelected ? 'var(--text-primary)' : 'inherit' }}>
                            {item.title}
                          </div>
                          {item.subtitle && (
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              {item.subtitle}
                            </div>
                          )}
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{item.category}</span>
                        {isSelected && <Icon name="chevron-right" size={14} style={{ color: 'var(--accent)' }} />}
                      </div>
                    </button>
                  )
                })
              )}
            </div>

            {/* Footer Hints */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0.65rem 1.25rem',
                background: 'var(--bg-surface-raised)',
                borderTop: '1px solid var(--border-subtle)',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
              }}
            >
              <div style={{ display: 'flex', gap: '1rem' }}>
                <span>↑↓ Pilih</span>
                <span>↵ Eksekusi</span>
                <span>ESC Tutup</span>
              </div>
              <span>Cortex AI Studio</span>
            </div>
          </div>
        </div>
      )}
    </CommandPaletteContext.Provider>
  )
}
