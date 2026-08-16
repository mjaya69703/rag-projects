import React, { useEffect, useRef, useState } from 'react'
import { useSessions } from '../context/SessionsContext'
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Icon,
  Modal,
  PromptDialog,
  SourceCard,
  Spinner,
  Markdown,
} from '../shared/components'
import { useToast } from '../shared/hooks'
import { chatService, documentService } from '../shared/services'
import type { DocumentInfo, Message, SourceRef } from '../shared/types'

export default function Chat() {
  const { addToast } = useToast()
  const {
    sessions,
    activeId,
    activeSession,
    messages,
    sendMessage,
    streamMessage,
    renameSession,
    deleteSession,
    selectSession,
    createSession,
  } = useSessions()

  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [selectedDoc, setSelectedDoc] = useState<string>('')
  const [chatMode, setChatMode] = useState<'sliding' | 'summary'>('sliding')

  // Modals
  const [isRenameOpen, setIsRenameOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    loadDocuments()
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isStreaming])

  const loadDocuments = async () => {
    try {
      const res = await documentService.listDocuments()
      setDocuments(res.documents || [])
    } catch {
      // ignore
    }
  }

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    const text = input.trim()
    if (!text || isStreaming) return

    setInput('')
    setIsStreaming(true)

    try {
      if (streamMessage) {
        await streamMessage(text, {
          source: selectedDoc || undefined,
          mode: chatMode,
        })
      } else {
        await sendMessage(text)
      }
    } catch (err: any) {
      addToast(err.message || 'Gagal mengirim pesan.', 'error')
    } finally {
      setIsStreaming(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleQuickPrompt = (promptText: string) => {
    setInput(promptText)
    textareaRef.current?.focus()
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {/* Session Title Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          paddingBottom: '0.75rem',
          borderBottom: '1px solid var(--border-subtle)',
          marginBottom: '0.75rem',
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', minWidth: '0' }}>
          <h2 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '240px' }}>
            {activeSession ? activeSession.title : 'Chat Studio'}
          </h2>
          <Badge variant="primary" size="sm">
            {chatMode === 'sliding' ? 'Sliding' : 'Summary'}
          </Badge>
          {selectedDoc && (
            <Badge variant="secondary" size="sm" title={selectedDoc}>
              📄 {selectedDoc.length > 15 ? `${selectedDoc.substring(0, 15)}…` : selectedDoc}
            </Badge>
          )}
        </div>

        {activeSession && (
          <div style={{ display: 'flex', gap: '0.35rem' }}>
            <Button
              variant="ghost"
              size="sm"
              icon="edit"
              onClick={() => setIsRenameOpen(true)}
              title="Ubah judul percakapan"
            >
              Ubah
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon="trash"
              onClick={() => setIsDeleteOpen(true)}
              title="Hapus percakapan ini"
            >
              Hapus
            </Button>
          </div>
        )}
      </div>

      {/* Messages Stream Container */}
      <div style={{ flex: 1, overflowY: 'auto', paddingRight: '0.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {messages.length === 0 ? (
          <div style={{ margin: 'auto 0', padding: '1.5rem 0' }}>
            <EmptyState
              icon="brain"
              title="Mulai Percakapan dengan Cortex"
              description="Tanyakan apa pun seputar dokumen yang telah Anda unggah. Cortex akan menjawab secara presisi dengan sitasi sumber."
            />
            {/* Quick Suggestion Chips */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', flexWrap: 'wrap', marginTop: '1.25rem', padding: '0 0.5rem' }}>
              <Button
                variant="secondary"
                size="sm"
                icon="sparkles"
                onClick={() => handleQuickPrompt('Berikan ringkasan poin-poin penting dari seluruh materi yang terindeks.')}
              >
                Ringkas materi utama
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon="quiz"
                onClick={() => handleQuickPrompt('Buatkan 3 pertanyaan penting dari dokumen ini untuk menguji pemahaman saya.')}
              >
                Buatkan pertanyaan uji
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon="glossary"
                onClick={() => handleQuickPrompt('Jelaskan istilah-istilah teknis kunci beserta definisinya.')}
              >
                Daftar istilah teknis
              </Button>
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => {
            const isUser = msg.role === 'user'
            return (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  gap: '1rem',
                  alignItems: 'flex-start',
                  padding: '1.25rem',
                  borderRadius: 'var(--radius-lg)',
                  background: isUser ? 'var(--bg-surface-raised)' : 'var(--glass-bg)',
                  border: `1px solid ${isUser ? 'var(--border-subtle)' : 'var(--glass-border)'}`,
                }}
              >
                {/* Avatar Icon */}
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: 'var(--radius-md)',
                    background: isUser ? 'var(--bg-surface)' : 'linear-gradient(135deg, var(--accent) 0%, var(--cyan) 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                    flexShrink: 0,
                    fontWeight: '700',
                    fontSize: '0.75rem',
                    boxShadow: isUser ? 'none' : '0 4px 14px var(--accent-glow)',
                  }}
                >
                  {isUser ? 'YOU' : <Icon name="sparkles" size={16} />}
                </div>

                {/* Content */}
                <div style={{ flex: 1, overflow: 'hidden', minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                    <span style={{ fontWeight: '700', fontSize: '0.85rem', color: isUser ? 'var(--text-primary)' : 'var(--accent)' }}>
                      {isUser ? 'Anda' : 'Cortex AI'}
                    </span>
                    {msg.created_at && (
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        {msg.created_at.substring(11, 16)}
                      </span>
                    )}
                  </div>

                  {isUser ? (
                    <div
                      style={{
                        fontSize: '0.92rem',
                        lineHeight: '1.65',
                        color: 'var(--text-primary)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        userSelect: 'text',
                      }}
                    >
                      {msg.content}
                    </div>
                  ) : (
                    <Markdown content={msg.content} />
                  )}

                  {/* Sources Accordion */}
                  {msg.sources && msg.sources.length > 0 && (
                    <div style={{ marginTop: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      <div style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                        📚 Sumber Rujukan Terverifikasi ({msg.sources.length}):
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.5rem' }}>
                        {msg.sources.map((s, sIdx) => (
                          <SourceCard key={sIdx} source={s} index={sIdx} />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )
          })
        )}

        {isStreaming && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 1rem', color: 'var(--accent)' }}>
            <Spinner size="sm" />
            <span style={{ fontSize: '0.85rem', fontWeight: '500' }}>Cortex sedang menganalisis dokumen dan merangkai jawaban...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Floating Prompt Input Bar */}
      <div
        style={{
          marginTop: '0.75rem',
          background: 'var(--glass-bg)',
          backdropFilter: 'var(--glass-blur)',
          WebkitBackdropFilter: 'var(--glass-blur)',
          border: '1px solid var(--glass-border)',
          borderRadius: 'var(--radius-xl)',
          padding: '0.65rem 0.85rem',
          boxShadow: 'var(--shadow-md)',
        }}
      >
        {/* Controls Row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem', flexWrap: 'wrap', gap: '0.4rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
            <select
              value={selectedDoc}
              onChange={(e) => setSelectedDoc(e.target.value)}
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)',
                fontSize: '0.78rem',
                padding: '0.25rem 0.5rem',
                borderRadius: 'var(--radius-sm)',
                maxWidth: '160px',
              }}
            >
              <option value="">Semua Dokumen</option>
              {documents.map((d) => (
                <option key={d.source} value={d.source}>
                  {d.source}
                </option>
              ))}
            </select>

            <button
              type="button"
              onClick={() => setChatMode(chatMode === 'sliding' ? 'summary' : 'sliding')}
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-secondary)',
                fontSize: '0.78rem',
                padding: '0.25rem 0.5rem',
                borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Mode: {chatMode === 'sliding' ? 'Sliding' : 'Summary'}
            </button>
          </div>

          <span className="top-bar-breadcrumb-parent" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Tekan <kbd style={{ padding: '0.1rem 0.35rem', borderRadius: '4px', background: 'var(--bg-surface)', border: '1px solid var(--border-default)' }}>Enter</kbd> kirim
          </span>
        </div>

        {/* Input Textarea & Send Button */}
        <form onSubmit={handleSend} style={{ display: 'flex', alignItems: 'flex-end', gap: '0.5rem' }}>
          <textarea
            ref={textareaRef}
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Tanyakan sesuatu tentang dokumen..."
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              resize: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.92rem',
              lineHeight: '1.4',
              padding: '0.25rem 0',
            }}
          />

          <Button
            type="submit"
            variant="primary"
            icon="send"
            disabled={!input.trim() || isStreaming}
            size="sm"
          >
            Kirim
          </Button>
        </form>
      </div>

      {/* Rename Dialog */}
      <PromptDialog
        isOpen={isRenameOpen}
        title="Ubah Nama Percakapan"
        defaultValue={activeSession?.title || ''}
        placeholder="Judul baru percakapan..."
        onConfirm={async (newTitle) => {
          if (activeSession) {
            await renameSession(activeSession.id, newTitle)
            setIsRenameOpen(false)
            addToast('Nama percakapan berhasil diperbarui!', 'success')
          }
        }}
        onCancel={() => setIsRenameOpen(false)}
      />

      {/* Delete Dialog */}
      <ConfirmDialog
        isOpen={isDeleteOpen}
        title="Hapus Percakapan?"
        description="Percakapan ini beserta seluruh riwayat pesannya akan dihapus secara permanen."
        confirmText="Hapus"
        onConfirm={async () => {
          if (activeSession) {
            await deleteSession(activeSession.id)
            setIsDeleteOpen(false)
            addToast('Percakapan berhasil dihapus.', 'info')
          }
        }}
        onCancel={() => setIsDeleteOpen(false)}
      />
    </div>
  )
}
