import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type Message, type SourceRef } from '../api'
import { useSessions } from '../context/SessionsContext'
import { Dialog } from '../components/Dialog'
import { Markdown } from '../components/Markdown'
import { usePageHeader } from '../components/PageHeader'
import { SourceAccordion, useAnnotationLoader } from '../components/SourceCard'
import { useToast } from '../components/Toast'
import { UploadDialog } from '../components/UploadDialog'

interface StreamEvent {
  type: 'meta' | 'delta' | 'done' | 'error'
  text?: string
  answer?: string
  sources?: SourceRef[]
  cached?: boolean
  grounded?: boolean
  document_missing?: boolean
  session?: unknown
  detail?: string
}

function MessageItem({
  message,
  annotations,
  onAnnotated,
  cached,
  grounded,
  documentMissing,
}: {
  message: Message
  annotations: Record<string, string>
  onAnnotated: () => void
  cached?: boolean
  grounded?: boolean
  documentMissing?: boolean
}) {
  const isUser = message.role === 'user'
  const showGrounding = !isUser && (documentMissing || grounded === false)
  return (
    <article className={`message ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">
        {isUser ? (
          'YOU'
        ) : (
          <svg className="icon" aria-hidden="true">
            <use href="#i-mark" />
          </svg>
        )}
      </div>
      <div className="message-content">
        <div className="message-meta">{isUser ? 'PERTANYAAN' : 'JAWABAN'}</div>
        {isUser ? (
          <div className="message-text">{message.content}</div>
        ) : (
          <>
            <div className={`message-text${showGrounding ? ' grounded-note' : ''}`}>
              {message.content ? (
                <Markdown content={message.content} />
              ) : (
                <div className="typing-dots" title="Sedang berpikir...">
                  <span />
                  <span />
                  <span />
                </div>
              )}
            </div>
            {showGrounding && !documentMissing && (
              <p className="grounded-notice">
                <Icon name="i-alert" /> Tidak ada materi yang cukup relevan — jawaban di atas bukan dari dokumen.
              </p>
            )}
            {cached && (
              <span className="cache-note">
                <svg className="icon" aria-hidden="true">
                  <use href="#i-zap" />
                </svg>{' '}
                dari semantic cache
              </span>
            )}
            {!!message.sources?.length && (
              <SourceAccordion sources={message.sources} annotations={annotations} onAnnotated={onAnnotated} />
            )}
          </>
        )}
      </div>
    </article>
  )
}

/** Halaman utama: chat (streaming) — sidebar & topbar di AppLayout. */
export default function Chat() {
  const toast = useToast()
  const navigate = useNavigate()
  const { annotations, loadAnnotations } = useAnnotationLoader()
  const {
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
    setMessages,
    setStreaming,
    refreshAll,
  } = useSessions()

  const [question, setQuestion] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [categories, setCategories] = useState<CategoryInfo[]>([])
  const [mode, setMode] = useState('sliding')
  const [topK, setTopK] = useState(5)
  const [emptyHidden, setEmptyHidden] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [commandOpen, setCommandOpen] = useState(false)

  const chatRegionRef = useRef<HTMLElement>(null)
  const questionRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const lastAnswerRef = useRef({ cached: false, grounded: true, documentMissing: false })

  // Topbar: judul session + aksi rename/delete
  usePageHeader({
    eyebrow: 'RAG WORKSPACE',
    title: activeSession?.title || 'Chat baru',
    actions: (
      <>
        <button className="icon-button" type="button" aria-label="Ubah nama chat" title="Ubah nama" onClick={() => void renameSession()}>
          <svg className="icon" aria-hidden="true"><use href="#i-edit" /></svg>
        </button>
        <button className="icon-button danger" type="button" aria-label="Hapus chat" title="Hapus chat" onClick={() => void deleteSession()}>
          <svg className="icon" aria-hidden="true"><use href="#i-trash" /></svg>
        </button>
      </>
    ),
  })

  useEffect(() => {
    if (activeId) void selectSession(activeId)
    void loadAnnotations()
    void api<{ categories: CategoryInfo[] }>('/categories')
      .then((res) => setCategories(res.categories || []))
      .catch(() => setCategories([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId])

  useEffect(() => {
    const onKey = (event: globalThis.KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setCommandOpen(true)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => chatRegionRef.current?.scrollTo({ top: chatRegionRef.current.scrollHeight }))
  }, [])

  async function askQuestion(raw?: string) {
    const text = (raw ?? question).trim()
    if (!text || streaming) return
    if (!activeId) await createSession()
    setEmptyHidden(true)

    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }])
    setQuestion('')
    setStreaming(true)

    const controller = new AbortController()
    abortRef.current = controller
    let answer = ''
    let sources: SourceRef[] = []
    let cached = false
    let grounded = true
    let documentMissing = false

    const updateAssistant = (patch: Partial<Message>) => {
      setMessages((prev) => {
        const next = [...prev]
        const last = next[next.length - 1]
        if (last) next[next.length - 1] = { ...last, ...patch }
        return next
      })
    }

    try {
      const response = await fetch('/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: text,
          top_k: topK,
          source: sourceFilter || null,
          category: categoryFilter || null,
          session_id: activeId,
          mode,
        }),
        signal: controller.signal,
      })
      if (!response.ok || !response.body) {
        const body = await response.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail || `HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const records = buffer.split('\n\n')
        buffer = records.pop() || ''

        for (const record of records) {
          const line = record.split('\n').find((l) => l.startsWith('data:'))
          if (!line) continue
          const event = JSON.parse(line.slice(5)) as StreamEvent

          if (event.type === 'meta') {
            sources = event.sources || []
            cached = event.cached || false
            grounded = event.grounded !== false
            documentMissing = !!event.document_missing
          } else if (event.type === 'delta') {
            answer += event.text || ''
            updateAssistant({ content: answer })
            scrollToBottom()
          } else if (event.type === 'done') {
            answer = event.answer || answer
            updateAssistant({ content: answer || '(Tidak ada jawaban)' })
            if (activeId) await selectSession(activeId)
          } else if (event.type === 'error') {
            const err = new Error(event.detail || 'Gagal mendapatkan jawaban.')
            ;(err as unknown as { isLLM?: boolean }).isLLM = true
            throw err
          }
        }
      }

      updateAssistant({ content: answer, sources: sources.length ? sources : undefined })
      lastAnswerRef.current = { cached, grounded, documentMissing }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        const text2 = answer.trim() ? `${answer}\n\n— Jawaban dihentikan.` : '(Jawaban dihentikan.)'
        updateAssistant({ content: text2 })
      } else {
        updateAssistant({ content: `Tidak dapat menjawab: ${(error as Error).message}`, sources: [] })
      }
    } finally {
      abortRef.current = null
      setStreaming(false)
      void loadAnnotations()
      void refreshAll()
      setTimeout(() => questionRef.current?.focus(), 0)
    }
  }

  function onComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void askQuestion()
    }
  }

  function autoGrow(event: FormEvent<HTMLTextAreaElement>) {
    const el = event.currentTarget
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 176)}px`
  }

  const lastIndex = messages.length - 1

  return (
    <>
      <section className="chat-region" aria-live="polite" ref={chatRegionRef}>
        <div className="empty-state" hidden={emptyHidden}>
          <div className="empty-icon">
            <svg className="icon" aria-hidden="true"><use href="#i-mark" /></svg>
          </div>
          <p className="eyebrow">RAG RETRIEVAL ENGINE</p>
          <h2>Apa yang ingin Anda pelajari hari ini?</h2>
          <p>Unggah materi dokumen lalu ajukan pertanyaan. Jawaban akan langsung merujuk ke sumber paragraf dan halamannya.</p>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', marginTop: 'var(--space-4)' }}>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-subtle)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
              <Icon name="i-bulb" /> COBA PERTANYAAN CONTOH:
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: 'var(--space-2)' }}>
              {[
                'Apa isi ringkasan dokumen ini?',
                'Jelaskan poin-poin utama materi ini.',
                'Apa saja istilah penting yang dibahas?',
              ].map((qText) => (
                <button
                  key={qText}
                  type="button"
                  className="button button-secondary"
                  style={{ minHeight: '34px', padding: '0 0.75rem', fontSize: 'var(--text-xs)', borderRadius: 'var(--radius-pill)', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                  onClick={() => {
                    setQuestion(qText)
                    questionRef.current?.focus()
                  }}
                >
                  <Icon name="i-sparkles" /> {qText}
                </button>
              ))}
            </div>
          </div>

          <div className="empty-actions" style={{ marginTop: 'var(--space-5)' }}>
            <Link className="button button-primary" to="/library">
              <svg className="icon" aria-hidden="true"><use href="#i-upload" /></svg> Kelola & Tambah Dokumen
            </Link>
          </div>
        </div>
        <div className="message-list">
          {messages.map((message, i) => (
            <MessageItem
              key={i}
              message={message}
              annotations={annotations}
              onAnnotated={() => void loadAnnotations()}
              cached={i === lastIndex && lastAnswerRef.current.cached}
              grounded={i === lastIndex ? lastAnswerRef.current.grounded : undefined}
              documentMissing={i === lastIndex ? lastAnswerRef.current.documentMissing : undefined}
            />
          ))}
        </div>
      </section>

      <section className="composer-area" aria-label="Tulis pertanyaan">
        <div className="composer-container">
          <div className="context-strip">
            {categories.length > 0 && (
              <div className="pill-group">
                <label>
                  Kategori:
                  <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)}>
                    <option value="">Semua kategori</option>
                    {categories.map((cat) => (
                      <option key={cat.category} value={cat.category}>
                        {cat.category} ({cat.doc_count})
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            <div className="pill-group">
              <label>
                Dokumen:
                <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}>
                  <option value="">Semua dokumen</option>
                  {documents.map((doc) => (
                    <option key={doc.source} value={doc.source}>
                      {doc.source}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="pill-group">
              <label>
                Konteks:
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="sliding">Sliding window</option>
                  <option value="summary">Ringkasan + recent</option>
                </select>
              </label>
            </div>
            <div className="pill-group">
              <label>
                Top-k:
                <select value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
                  {[3, 5, 8, 10, 15].map((n) => (
                    <option key={n} value={n}>
                      {n}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <form
            className="composer"
            onSubmit={(e) => {
              e.preventDefault()
              void askQuestion()
            }}
          >
            <textarea
              ref={questionRef}
              rows={1}
              maxLength={2000}
              placeholder="Tanya isi dokumenmu… (cth: Apa isi materi VLAN ini?)"
              value={question}
              disabled={streaming}
              onChange={(e) => {
                setQuestion(e.target.value)
                autoGrow(e)
              }}
              onKeyDown={onComposerKeyDown}
            />
            <button className="stop-button" type="button" aria-label="Hentikan jawaban" hidden={!streaming} onClick={() => abortRef.current?.abort()}>
              <svg className="icon" aria-hidden="true"><use href="#i-close" /></svg> Batal
            </button>
            <button className="send-button" type="submit" disabled={streaming}>
              <span>{streaming ? 'Menjawab...' : 'Kirim'}</span>
              <svg className="icon" aria-hidden="true"><use href="#i-send" /></svg>
            </button>
          </form>
          <p className="composer-note">
            Tekan <strong>Enter</strong> untuk kirim · <strong>Shift+Enter</strong> untuk baris baru
          </p>
        </div>
      </section>

      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={() => void refreshAll()} />

      <Dialog open={commandOpen} onClose={() => setCommandOpen(false)}>
        <div className="command-card">
          <p className="command-heading">AKSI CEPAT</p>
          <div className="command-options">
            <button type="button" onClick={() => { setCommandOpen(false); void createSession(); }}>
              <span><svg className="icon" aria-hidden="true"><use href="#i-chat" /></svg> Chat baru</span>
            </button>
            <button type="button" onClick={() => { setCommandOpen(false); setUploadOpen(true); }}>
              <span><svg className="icon" aria-hidden="true"><use href="#i-upload" /></svg> Unggah dokumen</span>
            </button>
            {[
              { to: '/library', label: 'Library', icon: 'i-file' },
              { to: '/quiz', label: 'Quiz', icon: 'i-quiz' },
              { to: '/flashcards', label: 'Flashcards', icon: 'i-card' },
              { to: '/progress', label: 'Progress', icon: 'i-chart' },
              { to: '/settings', label: 'Settings', icon: 'i-theme' },
            ].map((item) => (
              <button key={item.to} type="button" onClick={() => { setCommandOpen(false); navigate(item.to); }}>
                <span><svg className="icon" aria-hidden="true"><use href={`#${item.icon}`} /></svg> {item.label}</span>
              </button>
            ))}
          </div>
        </div>
      </Dialog>
    </>
  )
}
