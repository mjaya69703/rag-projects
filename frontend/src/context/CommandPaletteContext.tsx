import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dialog } from '../components/Dialog'
import { Icon } from '../components/Icon'
import { UploadDialog } from '../components/UploadDialog'
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

const NAV_ITEMS = [
  { to: '/library', label: 'Library', icon: 'i-file' },
  { to: '/quiz', label: 'Quiz', icon: 'i-quiz' },
  { to: '/flashcards', label: 'Flashcards', icon: 'i-card' },
  { to: '/progress', label: 'Progress', icon: 'i-chart' },
  { to: '/settings', label: 'Settings', icon: 'i-theme' },
  { to: '/glossary', label: 'Glossary', icon: 'i-mark' },
]

/**
 * Command palette global (dulu hanya ada di halaman Chat).
 * Terbuka via Ctrl/Cmd+K di semua route atau tombol "Perintah" di sidebar.
 * Semua command lama dipertahankan: chat baru, unggah dokumen, dan navigasi.
 */
export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { createSession, refreshAll } = useSessions()
  const [open, setOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)

  const openCommandPalette = useCallback(() => setOpen(true), [])
  const closeCommandPalette = useCallback(() => setOpen(false), [])

  // Key listener global — berlaku di semua route, bukan hanya halaman Chat.
  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setOpen((current) => !current)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  function run(command: () => void) {
    setOpen(false)
    command()
  }

  return (
    <CommandPaletteContext.Provider value={{ openCommandPalette, closeCommandPalette }}>
      {children}

      <Dialog open={open} onClose={closeCommandPalette}>
        <div className="command-card">
          <p className="command-heading">AKSI CEPAT</p>
          <div className="command-options">
            <button
              type="button"
              onClick={() =>
                run(() => {
                  void createSession().then(() => navigate('/'))
                })
              }
            >
              <span>
                <Icon name="i-chat" /> Chat baru
              </span>
            </button>
            <button type="button" onClick={() => run(() => setUploadOpen(true))}>
              <span>
                <Icon name="i-upload" /> Unggah dokumen
              </span>
            </button>
            {NAV_ITEMS.map((item) => (
              <button key={item.to} type="button" onClick={() => run(() => navigate(item.to))}>
                <span>
                  <Icon name={item.icon} /> {item.label}
                </span>
              </button>
            ))}
          </div>
        </div>
      </Dialog>

      {/* Upload dialog global — dipakai command "Unggah dokumen" dari semua route. */}
      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={() => void refreshAll()} />
    </CommandPaletteContext.Provider>
  )
}
