import React, { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Icon,
  Input,
  Modal,
  PageHeader,
  PromptDialog,
  Spinner,
  StatCard,
} from '../shared/components'
import { useToast } from '../shared/hooks'
import { documentService } from '../shared/services'
import type { DocumentInfo } from '../shared/types'

function getFileBadge(source: string) {
  const lower = source.toLowerCase()
  if (lower.startsWith('http://') || lower.startsWith('https://')) {
    return { label: 'URL', color: 'var(--cyan)', bg: 'var(--cyan-bg)' }
  }
  if (lower.endsWith('.pdf')) {
    return { label: 'PDF', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' }
  }
  if (lower.endsWith('.md') || lower.endsWith('.markdown')) {
    return { label: 'MD', color: '#a855f7', bg: 'rgba(168, 85, 247, 0.1)' }
  }
  if (lower.endsWith('.docx')) {
    return { label: 'DOCX', color: '#3b82f6', bg: 'rgba(59, 130, 246, 0.1)' }
  }
  if (lower.endsWith('.pptx')) {
    return { label: 'PPTX', color: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' }
  }
  return { label: 'TXT', color: '#64748b', bg: 'rgba(100, 116, 139, 0.1)' }
}

export default function Library() {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [categories, setCategories] = useState<Record<string, string>>({})
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [isDragOver, setIsDragOver] = useState(false)

  // URL Ingest Modal
  const [isUrlModalOpen, setIsUrlModalOpen] = useState(false)
  const [ingestUrl, setIngestUrl] = useState('')
  const [ingestCat, setIngestCat] = useState('Umum')
  const [ingestingUrl, setIngestingUrl] = useState(false)

  // Edit Category Modal
  const [isEditCategoryOpen, setIsEditCategoryOpen] = useState(false)
  const [targetDoc, setTargetDoc] = useState<DocumentInfo | null>(null)

  // Delete Confirm Modal
  const [deleteDoc, setDeleteDoc] = useState<DocumentInfo | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    loadLibrary()
  }, [])

  useEffect(() => {
    const hasPending = documents.some((d) => d.status === 'queued' || d.status === 'processing')
    if (hasPending) {
      const timer = setInterval(() => {
        loadLibrary(true)
      }, 1500)
      return () => clearInterval(timer)
    }
  }, [documents])

  const loadLibrary = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const [docRes, catRes] = await Promise.all([
        documentService.listDocuments(),
        documentService.listCategories(),
      ])
      setDocuments(docRes.documents || [])
      setCategories(catRes.categories || {})
    } catch (err: any) {
      if (!silent) addToast(err.message || 'Gagal memuat daftar dokumen.', 'error')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const handleFileUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return
    setUploading(true)

    let successCount = 0
    for (let i = 0; i < files.length; i++) {
      const file = files[i]
      try {
        await documentService.uploadFile(file, file.name, 'Umum')
        successCount++
      } catch (err: any) {
        addToast(`Gagal mengunggah ${file.name}: ${err.message}`, 'error')
      }
    }

    if (successCount > 0) {
      addToast(`${successCount} file berhasil dimasukkan ke antrean ingestion!`, 'success')
      loadLibrary()
    }
    setUploading(false)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleIngestUrl = async () => {
    if (!ingestUrl.trim()) return
    setIngestingUrl(true)
    try {
      await documentService.ingestUrl(ingestUrl.trim(), undefined, ingestCat)
      addToast('Tautan web berhasil dijadwalkan untuk ingestion!', 'success')
      setIngestUrl('')
      setIsUrlModalOpen(false)
      loadLibrary()
    } catch (err: any) {
      addToast(err.message || 'Gagal memproses URL.', 'error')
    } finally {
      setIngestingUrl(false)
    }
  }

  const handleDeleteDocument = async () => {
    if (!deleteDoc) return
    setDeleting(true)
    try {
      await documentService.deleteDocument(deleteDoc.source, true)
      addToast(`Dokumen '${deleteDoc.source}' berhasil dihapus.`, 'success')
      setDeleteDoc(null)
      loadLibrary()
    } catch (err: any) {
      addToast(err.message || 'Gagal menghapus dokumen.', 'error')
    } finally {
      setDeleting(false)
    }
  }

  const uniqueCategories = ['all', ...Array.from(new Set(documents.map((d) => d.category || 'Umum')))]

  const filteredDocs = documents.filter((doc) => {
    const matchesCat = selectedCategory === 'all' || (doc.category || 'Umum') === selectedCategory
    const matchesSearch = doc.source.toLowerCase().includes(search.toLowerCase())
    return matchesCat && matchesSearch
  })

  const totalChunks = documents.reduce((acc, d) => acc + (d.chunks || 0), 0)

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      {/* Top Header */}
      <PageHeader
        title="Knowledge Library"
        subtitle="Pusat repositori materi pengetahuan yang terindeks dalam ChromaDB Vector Store."
        actions={
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <Button
              variant="secondary"
              icon="link"
              onClick={() => setIsUrlModalOpen(true)}
            >
              Ingest Web URL
            </Button>
            <Button
              variant="primary"
              icon="upload"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {uploading ? 'Mengunggah...' : 'Unggah File'}
            </Button>
          </div>
        }
      />

      {/* KPI Stats Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: '1rem' }}>
        <StatCard title="Total Dokumen" value={documents.length} icon="file" subtitle="Terdaftar di sistem" />
        <StatCard title="Total Chunks" value={totalChunks} icon="library" subtitle="Vektor terindeks" />
        <StatCard title="Kategori Unik" value={uniqueCategories.length - 1} icon="tag" subtitle="Kluster materi" />
      </div>

      {/* Interactive Drop Zone */}
      <div
        className="upload-dropzone"
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragOver(true)
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragOver(false)
          handleFileUpload(e.dataTransfer.files)
        }}
        style={{
          border: `2px dashed ${isDragOver ? 'var(--accent)' : 'var(--border-default)'}`,
          borderRadius: 'var(--radius-xl)',
          padding: '2.5rem 1.5rem',
          textAlign: 'center',
          background: isDragOver ? 'var(--accent-bg)' : 'var(--bg-surface)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '0.85rem',
          cursor: 'pointer',
          transition: 'all var(--dur-fast) var(--ease-spring)',
          boxShadow: isDragOver ? '0 0 30px var(--accent-glow)' : 'var(--shadow-sm)',
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.md,.txt,.docx,.pptx,.html"
          style={{ display: 'none' }}
          onChange={(e) => handleFileUpload(e.target.files)}
          disabled={uploading}
        />

        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '50%',
            background: 'var(--accent-bg)',
            color: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 16px var(--accent-glow)',
          }}
        >
          <Icon name="upload" size={24} />
        </div>

        <div>
          <div style={{ fontWeight: '700', fontSize: '1rem', color: 'var(--text-primary)' }}>
            {uploading ? 'Sedang Memproses Upload...' : 'Klik atau Tarik & Lepas File ke Sini'}
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            Mendukung PDF, Markdown, DOCX, PPTX, HTML, TXT (Maks. 50MB)
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.4rem', overflowX: 'auto', maxWidth: '100%', paddingBottom: '0.25rem' }}>
          {uniqueCategories.map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`badge ${selectedCategory === cat ? 'badge--primary' : 'badge--neutral'}`}
              style={{ cursor: 'pointer', fontSize: '0.8rem', padding: '0.35rem 0.75rem', whiteSpace: 'nowrap' }}
            >
              {cat === 'all' ? 'Semua Dokumen' : cat}
            </button>
          ))}
        </div>

        <div style={{ flex: '1 1 220px', minWidth: '180px' }}>
          <Input
            placeholder="Cari nama dokumen..."
            icon="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Document Grid Cards */}
      {loading ? (
        <Card style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
          <Spinner size="lg" text="Memuat repositori dokumen..." />
        </Card>
      ) : filteredDocs.length === 0 ? (
        <Card>
          <EmptyState
            icon="library"
            title="Tidak Ada Dokumen"
            description="Belum ada dokumen yang sesuai dengan pencarian atau filter kategori Anda."
          />
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 300px), 1fr))', gap: '1rem' }}>
          {filteredDocs.map((doc) => {
            const badge = getFileBadge(doc.source)
            return (
              <Card key={doc.source} padding="md" hover>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem', marginBottom: '0.85rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flex: 1, overflow: 'hidden' }}>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: '700',
                        padding: '0.2rem 0.5rem',
                        borderRadius: 'var(--radius-xs)',
                        color: badge.color,
                        background: badge.bg,
                        flexShrink: 0,
                      }}
                    >
                      {badge.label}
                    </span>
                    <span
                      style={{
                        fontWeight: '700',
                        fontSize: '0.92rem',
                        color: 'var(--text-primary)',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                      title={doc.source}
                    >
                      {doc.source}
                    </span>
                  </div>

                  <Badge variant={doc.status === 'ready' ? 'success' : doc.status === 'error' ? 'error' : 'secondary'} size="sm">
                    {doc.status || 'Ready'}
                  </Badge>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.82rem', color: 'var(--text-muted)', marginBottom: '0.85rem' }}>
                  <span>Kategori: <b style={{ color: 'var(--text-secondary)' }}>{doc.category || 'Umum'}</b></span>
                  <span><b style={{ color: 'var(--accent)' }}>{doc.chunks || 0}</b> Chunks</span>
                </div>

                {/* Quick Action Shortcuts */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.35rem', marginBottom: '0.65rem' }}>
                  <button
                    type="button"
                    onClick={() => navigate('/quiz')}
                    style={{
                      padding: '0.3rem 0.4rem',
                      background: 'var(--bg-surface-raised)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.72rem',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.25rem',
                    }}
                    title="Buat kuis dari dokumen ini"
                  >
                    🎯 Kuis
                  </button>

                  <button
                    type="button"
                    onClick={() => navigate('/flashcards')}
                    style={{
                      padding: '0.3rem 0.4rem',
                      background: 'var(--bg-surface-raised)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.72rem',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.25rem',
                    }}
                    title="Buat/latih flashcard dokumen ini"
                  >
                    🃏 Kartu
                  </button>

                  <button
                    type="button"
                    onClick={() => navigate('/glossary')}
                    style={{
                      padding: '0.3rem 0.4rem',
                      background: 'var(--bg-surface-raised)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.72rem',
                      fontWeight: '600',
                      color: 'var(--text-secondary)',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: '0.25rem',
                    }}
                    title="Ekstrak istilah glosarium dokumen ini"
                  >
                    📖 Istilah
                  </button>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.65rem' }}>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="chat"
                    onClick={() => navigate('/')}
                  >
                    Tanya AI
                  </Button>

                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="edit"
                      onClick={() => {
                        setTargetDoc(doc)
                        setIsEditCategoryOpen(true)
                      }}
                    >
                      Kategori
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="trash"
                      onClick={() => setDeleteDoc(doc)}
                    >
                      Hapus
                    </Button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* URL Ingest Modal */}
      <Modal
        isOpen={isUrlModalOpen}
        onClose={() => setIsUrlModalOpen(false)}
        title="Ingest Dokumen dari URL Web"
        subtitle="Sistem akan mengunduh dan mengekstrak teks aman (dilengkapi anti-SSRF firewall)."
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsUrlModalOpen(false)}>
              Batal
            </Button>
            <Button variant="primary" icon="link" onClick={handleIngestUrl} loading={ingestingUrl}>
              Mulai Ingest
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="URL Web Target"
            placeholder="https://example.com/documentation"
            value={ingestUrl}
            onChange={(e) => setIngestUrl(e.target.value)}
            autoFocus
          />
          <Input
            label="Kategori Materi"
            placeholder="Contoh: Python, Network, Tutorial"
            value={ingestCat}
            onChange={(e) => setIngestCat(e.target.value)}
          />
        </div>
      </Modal>

      {/* Edit Category Prompt */}
      <PromptDialog
        isOpen={isEditCategoryOpen}
        title={`Ubah Kategori: ${targetDoc?.source || ''}`}
        defaultValue={targetDoc?.category || 'Umum'}
        label="Nama Kategori Baru"
        onConfirm={async (newCat) => {
          if (targetDoc) {
            await documentService.setCategory(targetDoc.source, newCat)
            setIsEditCategoryOpen(false)
            addToast('Kategori dokumen berhasil diperbarui!', 'success')
            loadLibrary()
          }
        }}
        onCancel={() => setIsEditCategoryOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={!!deleteDoc}
        title={`Hapus Dokumen: ${deleteDoc?.source || ''}?`}
        description="Vektor embedding dari dokumen ini akan dihapus dari ChromaDB. Dokumen tidak akan dapat dicari lagi di chat RAG."
        confirmText="Hapus Permanen"
        loading={deleting}
        onConfirm={handleDeleteDocument}
        onCancel={() => setDeleteDoc(null)}
      />
    </div>
  )
}
