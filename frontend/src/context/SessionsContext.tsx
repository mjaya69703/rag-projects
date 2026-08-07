import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { api, type DocumentInfo, type Message, type Session } from '../api'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { PromptDialog } from '../components/PromptDialog'

interface SessionsContextValue {
  sessions: Session[]
  activeId: string | null
  activeSession: Session | null
  messages: Message[]
  documents: DocumentInfo[]
  streaming: boolean
  selectSession: (id: string) => Promise<void>
  createSession: () => Promise<void>
  renameSession: () => void
  deleteSession: () => void
  loadSessions: () => Promise<void>
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setStreaming: (value: boolean) => void
  refreshAll: () => Promise<void>
}

const SessionsContext = createContext<SessionsContextValue | null>(null)

export function useSessions() {
  const ctx = useContext(SessionsContext)
  if (!ctx) throw new Error('useSessions harus dipakai di dalam SessionsProvider')
  return ctx
}

export function SessionsProvider({ children }: { children: ReactNode }) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [activeId, setActiveId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [streaming, setStreaming] = useState(false)
  const streamingRef = useRef(false)
  streamingRef.current = streaming

  // State untuk custom modal
  const [renameOpen, setRenameOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [modalLoading, setModalLoading] = useState(false)

  const activeSession = sessions.find((s) => s.id === activeId) || null

  const loadSessions = useCallback(async () => {
    const data = await api<{ sessions: Session[] }>('/sessions/list')
    setSessions(data.sessions)
    setActiveId((current) =>
      current && data.sessions.some((s) => s.id === current) ? current : data.sessions[0]?.id || null,
    )
  }, [])

  const selectSession = useCallback(async (id: string) => {
    if (!id || streamingRef.current) return
    setActiveId(id)
    const data = await api<{ messages: Message[] }>(`/sessions/${encodeURIComponent(id)}/messages`)
    setMessages(data.messages || [])
  }, [])

  const createSession = useCallback(async () => {
    const data = await api<{ session: Session }>('/sessions/create', { method: 'POST' })
    setActiveId(data.session.id)
    await loadSessions()
    await selectSession(data.session.id)
  }, [loadSessions, selectSession])

  const renameSession = useCallback(() => {
    if (!activeId || !activeSession) return
    setRenameOpen(true)
  }, [activeId, activeSession])

  const handleConfirmRename = async (newTitle: string) => {
    if (!newTitle.trim() || !activeId) return
    setModalLoading(true)
    try {
      await api(`/sessions/${encodeURIComponent(activeId)}/rename`, {
        method: 'PUT',
        body: JSON.stringify({ title: newTitle.trim() }),
      })
      await loadSessions()
      setRenameOpen(false)
    } finally {
      setModalLoading(false)
    }
  }

  const deleteSession = useCallback(() => {
    if (!activeId || !activeSession) return
    setDeleteOpen(true)
  }, [activeId, activeSession])

  const handleConfirmDelete = async () => {
    if (!activeId) return
    setModalLoading(true)
    try {
      await api(`/sessions/${encodeURIComponent(activeId)}`, { method: 'DELETE' })
      setActiveId(null)
      await loadSessions()
      setDeleteOpen(false)
      if (sessions.length > 1) {
        const remaining = sessions.filter((s) => s.id !== activeId)
        if (remaining[0]) await selectSession(remaining[0].id)
      } else {
        await createSession()
      }
    } finally {
      setModalLoading(false)
    }
  }

  const refreshAll = useCallback(async () => {
    await loadSessions()
    const docs = await api<{ documents: DocumentInfo[] }>('/documents')
    setDocuments(docs.documents)
  }, [loadSessions])

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  const value: SessionsContextValue = {
    sessions,
    activeId,
    activeSession,
    messages,
    documents,
    streaming,
    selectSession,
    createSession,
    renameSession,
    deleteSession,
    loadSessions,
    setMessages,
    setStreaming,
    refreshAll,
  }

  return (
    <SessionsContext.Provider value={value}>
      {children}

      {/* Modal Custom Rename Sesi */}
      <PromptDialog
        open={renameOpen}
        title="Ubah Nama Percakapan"
        message="Masukkan nama baru untuk percakapan ini:"
        defaultValue={activeSession?.title || ''}
        placeholder="Contoh: Diskusi VLAN & Subnetting"
        confirmText="Simpan Nama"
        loading={modalLoading}
        onConfirm={(val) => void handleConfirmRename(val)}
        onClose={() => setRenameOpen(false)}
      />

      {/* Modal Custom Hapus Sesi */}
      <ConfirmDialog
        open={deleteOpen}
        title="Hapus Percakapan?"
        message={`Apakah Anda yakin ingin menghapus "${activeSession?.title}"? Riwayat pesan percakapan ini tidak dapat dikembalikan.`}
        confirmText="Hapus Percakapan"
        danger
        loading={modalLoading}
        onConfirm={() => void handleConfirmDelete()}
        onClose={() => setDeleteOpen(false)}
      />
    </SessionsContext.Provider>
  )
}
