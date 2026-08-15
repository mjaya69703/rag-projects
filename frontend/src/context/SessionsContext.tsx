import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { chatService, documentService } from '../shared/services'
import type { DocumentInfo, Message, Session } from '../shared/types'

interface StreamOptions {
  source?: string
  mode?: 'sliding' | 'summary'
}

interface SessionsContextValue {
  sessions: Session[]
  activeId: string | null
  activeSession: Session | null
  messages: Message[]
  documents: DocumentInfo[]
  streaming: boolean
  selectSession: (id: string) => Promise<void>
  createSession: () => void
  renameSession: (id: string, newTitle: string) => Promise<void>
  deleteSession: (id: string) => Promise<void>
  sendMessage: (text: string, options?: StreamOptions) => Promise<void>
  streamMessage: (text: string, options?: StreamOptions) => Promise<void>
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

  const activeSession = sessions.find((s) => s.id === activeId) || null

  const loadSessions = useCallback(async () => {
    try {
      const data = await chatService.listSessions()
      setSessions(data.sessions || [])
    } catch {
      // ignore
    }
  }, [])

  const selectSession = useCallback(async (id: string) => {
    if (!id || streamingRef.current) return
    setActiveId(id)
    try {
      const data = await chatService.getMessages(id)
      setMessages(data.messages || [])
    } catch {
      setMessages([])
    }
  }, [])

  // LAZY SESSION CREATION: Cukup reset state lokal ke draft baru, TANPA memanggil API create session
  const createSession = useCallback(() => {
    if (streamingRef.current) return
    setActiveId(null)
    setMessages([])
  }, [])

  const renameSession = useCallback(async (id: string, newTitle: string) => {
    if (!newTitle.trim() || !id) return
    await chatService.renameSession(id, newTitle.trim())
    await loadSessions()
  }, [loadSessions])

  const deleteSession = useCallback(async (id: string) => {
    if (!id) return
    await chatService.deleteSession(id)
    setActiveId(null)
    setMessages([])
    await loadSessions()
  }, [loadSessions])

  const streamMessage = useCallback(async (text: string, options?: StreamOptions) => {
    if (!text.trim() || streamingRef.current) return

    let currentSessionId = activeId

    // Jika ini chat baru (activeId == null), buat session SEKARANG (saat pesan pertama dikirim)
    if (!currentSessionId) {
      const title = text.length > 30 ? text.slice(0, 30) + '...' : text
      const newSess = await chatService.createSession(title)
      currentSessionId = newSess.session.id
      setActiveId(currentSessionId)
    }

    // Tambahkan pesan user ke UI
    const userMsg: Message = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setStreaming(true)

    // Siapkan placeholder response assistant
    const assistantMsg: Message = { role: 'assistant', content: '' }
    setMessages((prev) => [...prev, assistantMsg])

    try {
      const token = localStorage.getItem('kb_api_token') || ''
      const res = await fetch('/query/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          question: text,
          session_id: currentSessionId,
          source: options?.source || null,
          mode: options?.mode || 'sliding',
        }),
      })

      if (!res.ok || !res.body) {
        throw new Error(`HTTP error ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let accumulatedText = ''
      let sources: any[] = []

      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim()
            try {
              const parsed = JSON.parse(dataStr)
              if (parsed.type === 'delta' && parsed.text) {
                accumulatedText += parsed.text
                setMessages((prev) => {
                  const copy = [...prev]
                  const lastIdx = copy.length - 1
                  if (lastIdx >= 0 && copy[lastIdx].role === 'assistant') {
                    copy[lastIdx] = { ...copy[lastIdx], content: accumulatedText }
                  }
                  return copy
                })
              } else if (parsed.type === 'done') {
                if (parsed.sources) {
                  sources = parsed.sources
                }
              }
            } catch {
              // ignore json parse chunk
            }
          }
        }
      }

      // Final update with sources
      setMessages((prev) => {
        const copy = [...prev]
        const lastIdx = copy.length - 1
        if (lastIdx >= 0 && copy[lastIdx].role === 'assistant') {
          copy[lastIdx] = {
            ...copy[lastIdx],
            content: accumulatedText || copy[lastIdx].content,
            sources: sources.length > 0 ? sources : undefined,
          }
        }
        return copy
      })

      // Reload session list to show updated title or new chat in sidebar
      await loadSessions()
    } catch (err: any) {
      setMessages((prev) => {
        const copy = [...prev]
        const lastIdx = copy.length - 1
        if (lastIdx >= 0 && copy[lastIdx].role === 'assistant') {
          copy[lastIdx] = { ...copy[lastIdx], content: `Terjadi kesalahan saat memproses jawaban: ${err.message}` }
        }
        return copy
      })
    } finally {
      setStreaming(false)
    }
  }, [activeId, loadSessions])

  const sendMessage = useCallback(async (text: string, options?: StreamOptions) => {
    return streamMessage(text, options)
  }, [streamMessage])

  const refreshAll = useCallback(async () => {
    await loadSessions()
    try {
      const docs = await documentService.listDocuments()
      setDocuments(docs.documents || [])
    } catch {
      // ignore
    }
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
    sendMessage,
    streamMessage,
    loadSessions,
    setMessages,
    setStreaming,
    refreshAll,
  }

  return (
    <SessionsContext.Provider value={value}>
      {children}
    </SessionsContext.Provider>
  )
}
