import React, { useEffect, useState } from 'react'
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
  Spinner,
} from '../shared/components'
import { useToast } from '../shared/hooks'
import { annotationsService } from '../shared/services/annotationsService'
import type { AnnotationItem } from '../shared/types'

function parseChunkKey(key: string): { source: string; chunkIndex: string } {
  const idx = key.lastIndexOf('#')
  if (idx === -1) return { source: key, chunkIndex: '' }
  return { source: key.slice(0, idx), chunkIndex: key.slice(idx + 1) }
}

function formatDate(iso?: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('id-ID', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

export default function Annotations() {
  const { addToast } = useToast()
  const [annotations, setAnnotations] = useState<AnnotationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [sourceFilter, setSourceFilter] = useState<string>('all')

  // Edit state
  const [editing, setEditing] = useState<AnnotationItem | null>(null)
  const [editText, setEditText] = useState('')
  const [saving, setSaving] = useState(false)

  // Delete state
  const [deleting, setDeleting] = useState<AnnotationItem | null>(null)
  const [deletingBusy, setDeletingBusy] = useState(false)

  useEffect(() => {
    loadAnnotations()
  }, [])

  const loadAnnotations = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await annotationsService.listAnnotations()
      setAnnotations(res.annotations || [])
    } catch (err: any) {
      if (!silent) addToast(err.message || 'Gagal memuat catatan anotasi.', 'error')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const uniqueSources = Array.from(
    new Set(annotations.map((a) => parseChunkKey(a.chunk_key).source))
  ).sort()

  const filtered = annotations.filter((a) => {
    const { source } = parseChunkKey(a.chunk_key)
    const matchesSource = sourceFilter === 'all' || source === sourceFilter
    const matchesSearch = `${source} ${a.note}`.toLowerCase().includes(search.toLowerCase())
    return matchesSource && matchesSearch
  })

  const handleSave = async () => {
    if (!editing) return
    setSaving(true)
    try {
      await annotationsService.upsertNote(editing.chunk_key, editText)
      addToast('Catatan berhasil disimpan!', 'success')
      setEditing(null)
      loadAnnotations(true)
    } catch (err: any) {
      addToast(err.message || 'Gagal menyimpan catatan.', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleting) return
    setDeletingBusy(true)
    try {
      await annotationsService.deleteNote(deleting.chunk_key)
      addToast('Catatan dihapus.', 'success')
      setDeleting(null)
      loadAnnotations(true)
    } catch (err: any) {
      addToast(err.message || 'Gagal menghapus catatan.', 'error')
    } finally {
      setDeletingBusy(false)
    }
  }

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <PageHeader
        title="Catatan Anotasi"
        subtitle="Catatan pribadi Anda yang menempel pada dokumen. Saat potongan terkait terbawa ke jawaban RAG, catatannya ikut ditampilkan supaya Anda ingat konteksnya."
        actions={
          <Button variant="secondary" icon="refresh" onClick={() => loadAnnotations()}>
            Muat Ulang
          </Button>
        }
      />

      {/* How-to hint */}
      <Card padding="sm">
        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'flex-start', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
          <Icon name="info" size="md" />
          <div>
            <b>Cara pakai:</b> buka <b>Library</b>, pilih dokumen, lalu klik tombol <b>Catatan</b> di kartunya. Tulis catatan pribadi, simpan — dan catatan itu akan muncul di halaman ini.
          </div>
        </div>
      </Card>

      {/* Filter & Search */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.4rem', overflowX: 'auto', maxWidth: '100%', paddingBottom: '0.25rem' }}>
          <button
            type="button"
            onClick={() => setSourceFilter('all')}
            className={`badge ${sourceFilter === 'all' ? 'badge--primary' : 'badge--neutral'}`}
            style={{ cursor: 'pointer', fontSize: '0.8rem', padding: '0.35rem 0.75rem', whiteSpace: 'nowrap' }}
          >
            Semua Sumber
          </button>
          {uniqueSources.map((src) => (
            <button
              key={src}
              type="button"
              onClick={() => setSourceFilter(src)}
              className={`badge ${sourceFilter === src ? 'badge--primary' : 'badge--neutral'}`}
              style={{ cursor: 'pointer', fontSize: '0.8rem', padding: '0.35rem 0.75rem', whiteSpace: 'nowrap' }}
            >
              {src}
            </button>
          ))}
        </div>

        <div style={{ flex: '1 1 220px', minWidth: '180px' }}>
          <Input
            placeholder="Cari catatan..."
            icon="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* List */}
      {loading ? (
        <Card style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
          <Spinner size="lg" text="Memuat catatan anotasi..." />
        </Card>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="note"
            title="Belum Ada Catatan Anotasi"
            description="Buka Library, klik tombol Catatan pada sebuah dokumen, tulis catatan pribadi, lalu simpan. Catatannya akan muncul di sini."
          />
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          {filtered.map((a) => {
            const { source, chunkIndex } = parseChunkKey(a.chunk_key)
            return (
              <Card key={a.chunk_key} padding="md" hover>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: '200px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem', flexWrap: 'wrap' }}>
                      <Badge variant="primary" size="sm">Chunk #{chunkIndex || '?'}</Badge>
                      <span style={{ fontWeight: '600', fontSize: '0.85rem', color: 'var(--text-primary)' }}>{source}</span>
                    </div>
                    <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: '1.55', whiteSpace: 'pre-wrap' }}>
                      {a.note}
                    </p>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.5rem' }}>
                      Diperbarui: {formatDate(a.updated_at)}
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    <Button
                      variant="ghost"
                      size="sm"
                      icon="edit"
                      onClick={() => {
                        setEditing(a)
                        setEditText(a.note)
                      }}
                    >
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" icon="trash" onClick={() => setDeleting(a)}>
                      Hapus
                    </Button>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      )}

      {/* Edit Modal */}
      <Modal
        isOpen={!!editing}
        onClose={() => setEditing(null)}
        title="Edit Catatan Anotasi"
        subtitle={editing ? parseChunkKey(editing.chunk_key).source : undefined}
        maxWidth="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)} disabled={saving}>
              Batal
            </Button>
            <Button variant="primary" icon="check" onClick={handleSave} loading={saving}>
              Simpan Catatan
            </Button>
          </>
        }
      >
        <textarea
          className="form-input"
          rows={6}
          value={editText}
          onChange={(e) => setEditText(e.target.value)}
          placeholder="Tulis catatan pribadi Anda di sini..."
          autoFocus
          style={{ width: '100%', minHeight: '140px', resize: 'vertical' }}
        />
      </Modal>

      {/* Delete Confirm */}
      <ConfirmDialog
        isOpen={!!deleting}
        title="Hapus Catatan Anotasi?"
        description="Catatan ini akan dihapus permanen dari chunk dokumen."
        confirmText="Hapus Catatan"
        loading={deletingBusy}
        onConfirm={handleDelete}
        onCancel={() => setDeleting(null)}
      />
    </div>
  )
}