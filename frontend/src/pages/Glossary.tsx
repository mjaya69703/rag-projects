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
  Select,
  Spinner,
} from '../shared/components'
import { useToast } from '../shared/hooks'
import { documentService, glossaryService } from '../shared/services'
import type { DocumentInfo, GlossaryTerm } from '../shared/types'

export default function Glossary() {
  const { addToast } = useToast()
  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterDoc, setFilterDoc] = useState('')
  const [filterVerified, setFilterVerified] = useState<string>('')
  const [selectedCategory, setSelectedCategory] = useState<string>('')

  // Add / Edit Modal
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [editingTerm, setEditingTerm] = useState<Partial<GlossaryTerm>>({
    term: '',
    definition: '',
    source: '',
    category: 'Umum',
    verified: true,
  })
  const [savingTerm, setSavingTerm] = useState(false)

  // Delete Confirm
  const [deleteTarget, setDeleteTarget] = useState<GlossaryTerm | null>(null)
  const [deleting, setDeleting] = useState(false)

  // AI Candidates Extraction Modal
  const [isCandidatesModalOpen, setIsCandidatesModalOpen] = useState(false)
  const [extractDoc, setExtractDoc] = useState('')
  const [extractLimit, setExtractLimit] = useState(10)
  const [candidates, setCandidates] = useState<GlossaryTerm[]>([])
  const [loadingCandidates, setLoadingCandidates] = useState(false)
  const [promotingAll, setPromotingAll] = useState(false)
  const [extractError, setExtractError] = useState<string | null>(null)

  useEffect(() => {
    loadGlossary()
    loadDocuments()
  }, [search, filterDoc, filterVerified])

  const loadDocuments = async () => {
    try {
      const res = await documentService.listDocuments()
      setDocuments(res.documents || [])
    } catch {
      // ignore
    }
  }

  const loadGlossary = async () => {
    setLoading(true)
    try {
      const verifiedParam = filterVerified === 'true' ? true : filterVerified === 'false' ? false : null
      const res = await glossaryService.listGlossary(search, filterDoc || null, verifiedParam)
      setTerms(res.terms || [])
    } catch (err: any) {
      addToast(err.message || 'Gagal memuat daftar glossary.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleVerify = async (item: GlossaryTerm) => {
    if (!item.id) return
    try {
      const res = await glossaryService.toggleVerify(item.id)
      const newStatus = res.term?.verified ? 'Terverifikasi' : 'Draf'
      addToast(`Status '${item.term}' diubah menjadi ${newStatus}!`, 'success')
      setTerms((prev) =>
        prev.map((t) => (t.id === item.id ? { ...t, verified: res.term?.verified ?? !t.verified } : t))
      )
    } catch (err: any) {
      addToast(err.message || 'Gagal mengubah status verifikasi.', 'error')
    }
  }

  const handleSaveTerm = async () => {
    if (!editingTerm.term?.trim() || !editingTerm.definition?.trim()) {
      addToast('Istilah dan definisi wajib diisi.', 'warning')
      return
    }

    setSavingTerm(true)
    try {
      if (editingTerm.id) {
        await glossaryService.updateTerm(editingTerm.id, editingTerm)
        addToast(`Istilah '${editingTerm.term}' berhasil diperbarui!`, 'success')
      } else {
        await glossaryService.createTerm(editingTerm)
        addToast('Istilah baru berhasil disimpan!', 'success')
      }
      setIsEditModalOpen(false)
      loadGlossary()
    } catch (err: any) {
      addToast(err.message || 'Gagal menyimpan istilah.', 'error')
    } finally {
      setSavingTerm(false)
    }
  }

  const handleStartExtraction = async () => {
    if (!extractDoc) {
      setExtractError('Pilih dokumen sumber dulu sebelum menjalankan AI.')
      return
    }
    setExtractError(null)
    setLoadingCandidates(true)
    try {
      const res = await glossaryService.getCandidates(extractDoc, extractLimit)
      const incoming = res.candidates || []
      const fresh = incoming.filter((c: any) => !c.exists)
      const skipped = incoming.length - fresh.length
      setCandidates(fresh)
      if (fresh.length === 0 && skipped > 0) {
        addToast(
          `Semua ${skipped} istilah yang disarankan sudah ada di glosarium.`,
          'info',
        )
      } else if (fresh.length === 0) {
        addToast('Tidak ditemukan istilah baru dari dokumen ini.', 'info')
      } else if (skipped > 0) {
        addToast(
          `${skipped} istilah yang sudah ada di glosarium otomatis disembunyikan.`,
          'info',
        )
      }
    } catch (err: any) {
      setExtractError(err.message || 'Gagal mengekstrak kandidat istilah.')
    } finally {
      setLoadingCandidates(false)
    }
  }

  const handlePromoteCandidate = async (candidate: GlossaryTerm) => {
    try {
      await glossaryService.createTerm({ ...candidate, verified: true })
      addToast(`'${candidate.term}' berhasil dipromosikan ke glosarium!`, 'success')
      setCandidates((prev) => prev.filter((c) => c.term !== candidate.term))
      loadGlossary()
    } catch (err: any) {
      const msg = err?.message || ''
      if (msg.toLowerCase().includes('sudah ada') || msg.toLowerCase().includes('duplicate')) {
        addToast(`'${candidate.term}' sudah ada di glosarium — dilewati.`, 'info')
        setCandidates((prev) => prev.filter((c) => c.term !== candidate.term))
      } else {
        addToast(msg || 'Gagal menambahkan istilah.', 'error')
      }
    }
  }

  const handlePromoteAll = async () => {
    if (candidates.length === 0) return
    setPromotingAll(true)
    let added = 0
    let skipped = 0
    for (const c of candidates) {
      try {
        await glossaryService.createTerm({ ...c, verified: true })
        added++
      } catch (err: any) {
        const msg = err?.message || ''
        if (
          msg.toLowerCase().includes('sudah ada') ||
          msg.toLowerCase().includes('duplicate')
        ) {
          skipped++
        }
      }
    }
    setPromotingAll(false)
    if (added > 0 && skipped > 0) {
      addToast(
        `${added} istilah ditambahkan, ${skipped} sudah ada dan dilewati.`,
        'success',
      )
    } else if (added > 0) {
      addToast(`${added} istilah berhasil dipromosikan ke glosarium!`, 'success')
    } else if (skipped > 0) {
      addToast(`${skipped} istilah sudah ada di glosarium — tidak ada yang ditambahkan.`, 'info')
    }
    setCandidates([])
    setIsCandidatesModalOpen(false)
    loadGlossary()
  }

  const handleDeleteTerm = async () => {
    if (!deleteTarget || !deleteTarget.id) return
    setDeleting(true)
    try {
      await glossaryService.deleteTerm(deleteTarget.id)
      addToast(`Istilah '${deleteTarget.term}' berhasil dihapus.`, 'info')
      setDeleteTarget(null)
      loadGlossary()
    } catch (err: any) {
      addToast(err.message || 'Gagal menghapus istilah.', 'error')
    } finally {
      setDeleting(false)
    }
  }

  // Categories list
  const categories = Array.from(new Set(terms.map((t) => t.category || 'Umum'))).filter(Boolean)
  const filteredTerms = terms.filter((t) => {
    if (selectedCategory && (t.category || 'Umum') !== selectedCategory) return false
    return true
  })

  return (
    <div className="page-container">
      <PageHeader
        title="Knowledge Glossary"
        subtitle="Kamus definisi dan istilah kunci yang terindeks langsung dari seluruh dokumen materi Anda."
        actions={
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <Button
              variant="secondary"
              icon="sparkles"
              onClick={() => {
                setExtractDoc(filterDoc || (documents[0]?.source ?? ''))
                setCandidates([])
                setExtractError(null)
                setIsCandidatesModalOpen(true)
              }}
            >
              Ekstrak Istilah dari Dokumen
            </Button>
            <Button
              variant="primary"
              icon="plus"
              onClick={() => {
                setEditingTerm({ term: '', definition: '', source: filterDoc || '', category: 'Umum', verified: true })
                setIsEditModalOpen(true)
              }}
            >
              Tambah Istilah Baru
            </Button>
          </div>
        }
      />

      {/* Filter Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
        <Input
          placeholder="Cari istilah atau isi definisi..."
          icon="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          value={filterDoc}
          onChange={(e) => setFilterDoc(e.target.value)}
          options={[
            { value: '', label: 'Semua Sumber Dokumen' },
            ...documents.map((d) => ({ value: d.source, label: d.source })),
          ]}
        />
        <Select
          value={filterVerified}
          onChange={(e) => setFilterVerified(e.target.value)}
          options={[
            { value: '', label: 'Semua Status Verifikasi' },
            { value: 'true', label: 'Hanya Terverifikasi' },
            { value: 'false', label: 'Hanya Draf / Belum Verifikasi' },
          ]}
        />
      </div>

      {/* Category Pills Filter */}
      {categories.length > 0 && (
        <div style={{ display: 'flex', gap: '0.4rem', marginBottom: '1.25rem', overflowX: 'auto', maxWidth: '100%', paddingBottom: '0.25rem', alignItems: 'center' }}>
          <span style={{ fontSize: '0.78rem', fontWeight: '700', color: 'var(--text-muted)', textTransform: 'uppercase', marginRight: '0.25rem', whiteSpace: 'nowrap' }}>
            Kategori:
          </span>
          <button
            type="button"
            onClick={() => setSelectedCategory('')}
            style={{
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-sm)',
              background: selectedCategory === '' ? 'var(--accent)' : 'var(--bg-surface-raised)',
              color: selectedCategory === '' ? '#fff' : 'var(--text-secondary)',
              border: `1px solid ${selectedCategory === '' ? 'var(--accent)' : 'var(--border-subtle)'}`,
              fontSize: '0.8rem',
              fontWeight: '600',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            Semua ({terms.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              style={{
                padding: '0.35rem 0.75rem',
                borderRadius: 'var(--radius-sm)',
                background: selectedCategory === cat ? 'var(--accent)' : 'var(--bg-surface-raised)',
                color: selectedCategory === cat ? '#fff' : 'var(--text-secondary)',
                border: `1px solid ${selectedCategory === cat ? 'var(--accent)' : 'var(--border-subtle)'}`,
                fontSize: '0.8rem',
                fontWeight: '600',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {cat} ({terms.filter((t) => (t.category || 'Umum') === cat).length})
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <Card style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
          <Spinner size="lg" text="Memuat istilah glosarium..." />
        </Card>
      ) : filteredTerms.length === 0 ? (
        <Card>
          <EmptyState
            icon="glossary"
            title="Tidak Ada Istilah Ditemukan"
            description="Belum ada istilah yang cocok dengan kriteria pencarian Anda. Tambah istilah secara manual atau ekstrak otomatis via AI."
            actionLabel="Ekstrak Istilah dari Dokumen"
            actionIcon="sparkles"
            onAction={() => {
              setExtractDoc(filterDoc || (documents[0]?.source ?? ''))
              setCandidates([])
              setExtractError(null)
              setIsCandidatesModalOpen(true)
            }}
          />
        </Card>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 300px), 1fr))', gap: '1rem' }}>
          {filteredTerms.map((item, idx) => (
            <Card key={item.id || idx} padding="md" hover>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', gap: '0.5rem' }}>
                <div>
                  <h4 style={{ fontSize: '1.1rem', fontWeight: '700', color: 'var(--text-primary)', lineHeight: '1.3' }}>
                    {item.term}
                  </h4>
                  {item.category && item.category !== 'Umum' && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--accent)', fontWeight: '600' }}>
                      {item.category}
                    </span>
                  )}
                </div>

                {/* Actions: Toggle Verify, Edit, Delete */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <button
                    type="button"
                    onClick={() => handleToggleVerify(item)}
                    title={item.verified ? 'Klik untuk jadikan Draf' : 'Klik untuk Verifikasi'}
                    style={{
                      background: item.verified ? 'var(--success-bg)' : 'var(--bg-surface-raised)',
                      border: `1px solid ${item.verified ? 'var(--success)' : 'var(--border-default)'}`,
                      color: item.verified ? 'var(--success)' : 'var(--text-muted)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.2rem 0.5rem',
                      fontSize: '0.72rem',
                      fontWeight: '700',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.25rem',
                    }}
                  >
                    <Icon name={item.verified ? 'check' : 'plus'} size={12} />
                    {item.verified ? 'Terverifikasi' : 'Verifikasi'}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setEditingTerm(item)
                      setIsEditModalOpen(true)
                    }}
                    style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '3px' }}
                    title="Ubah Definisi"
                  >
                    <Icon name="edit" size={14} />
                  </button>

                  <button
                    type="button"
                    onClick={() => setDeleteTarget(item)}
                    style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '3px' }}
                    title="Hapus Istilah"
                  >
                    <Icon name="trash" size={14} />
                  </button>
                </div>
              </div>

              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '1rem' }}>
                {item.definition}
              </p>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.75rem', borderTop: '1px solid var(--border-subtle)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '200px' }}>
                  {item.source ? `📄 ${item.source}` : '🏷️ Umum'}
                </span>
                {item.page ? <span>Hal. {item.page}</span> : null}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Add / Edit Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title={editingTerm.id ? 'Ubah Istilah Glosarium' : 'Tambah Istilah Baru'}
        subtitle="Definisikan istilah kunci dan konsep materi secara presisi."
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsEditModalOpen(false)} disabled={savingTerm}>
              Batal
            </Button>
            <Button variant="primary" icon="check" onClick={handleSaveTerm} loading={savingTerm}>
              Simpan Istilah
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Istilah / Term"
            placeholder="Contoh: VLAN, BGP, Latency, DNS Record"
            value={editingTerm.term || ''}
            onChange={(e) => setEditingTerm({ ...editingTerm, term: e.target.value })}
          />

          <div className="form-group">
            <label className="form-label">Definisi Komprehensif</label>
            <textarea
              className="form-input"
              rows={4}
              placeholder="Tuliskan penjelasan dan definisi konsep..."
              value={editingTerm.definition || ''}
              onChange={(e) => setEditingTerm({ ...editingTerm, definition: e.target.value })}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <Input
              label="Kategori"
              placeholder="Contoh: Jaringan, Cloud, Sistem"
              value={editingTerm.category || 'Umum'}
              onChange={(e) => setEditingTerm({ ...editingTerm, category: e.target.value })}
            />
            <Select
              label="Dokumen Sumber"
              value={editingTerm.source || ''}
              onChange={(e) => setEditingTerm({ ...editingTerm, source: e.target.value })}
              options={[
                { value: '', label: 'Umum (Tanpa Dokumen Spesifik)' },
                ...documents.map((d) => ({ value: d.source, label: d.source })),
              ]}
            />
          </div>
        </div>
      </Modal>

      {/* AI Extraction Modal */}
      <Modal
        isOpen={isCandidatesModalOpen}
        onClose={() => setIsCandidatesModalOpen(false)}
        title="Ekstrak Istilah dari Dokumen (AI)"
        subtitle="AI akan membaca isi dokumen dan mengekstrak istilah teknis penting secara otomatis."
        maxWidth="lg"
        footer={
          candidates.length > 0 ? (
            <>
              <Button variant="ghost" onClick={() => setIsCandidatesModalOpen(false)}>
                Tutup
              </Button>
              <Button
                variant="primary"
                icon="check"
                onClick={handlePromoteAll}
                loading={promotingAll}
              >
                Promosikan Semua ({candidates.length})
              </Button>
            </>
          ) : undefined
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Controls Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr auto', gap: '0.75rem', alignItems: 'flex-end', background: 'var(--bg-surface-raised)', padding: '1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
            <Select
              label="Pilih Dokumen Sumber (wajib)"
              value={extractDoc}
              onChange={(e) => {
                setExtractDoc(e.target.value)
                setExtractError(null)
              }}
              options={[
                { value: '', label: documents.length === 0 ? 'Belum ada dokumen terindeks' : '-- Pilih Dokumen --' },
                ...documents.map((d) => ({ value: d.source, label: d.source })),
              ]}
            />
            <Select
              label="Jumlah Istilah"
              value={String(extractLimit)}
              onChange={(e) => setExtractLimit(Number(e.target.value))}
              options={[
                { value: '5', label: '5 Istilah' },
                { value: '10', label: '10 Istilah' },
                { value: '15', label: '15 Istilah' },
                { value: '20', label: '20 Istilah' },
              ]}
            />
            <Button
              variant="primary"
              icon="sparkles"
              onClick={handleStartExtraction}
              loading={loadingCandidates}
              disabled={!extractDoc || loadingCandidates}
            >
              Ekstrak AI
            </Button>
          </div>
          {extractError && (
            <div
              role="alert"
              style={{
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                background: 'var(--danger-bg, rgba(220, 38, 38, 0.1))',
                border: '1px solid var(--danger, #dc2626)',
                color: 'var(--danger, #dc2626)',
                fontSize: '0.85rem',
              }}
            >
              {extractError}
            </div>
          )}

          {/* Results Area */}
          {loadingCandidates ? (
            <div style={{ padding: '3.5rem', display: 'flex', justifyContent: 'center' }}>
              <Spinner size="lg" text="Menganalisis dokumen dan mengekstrak istilah penting..." />
            </div>
          ) : candidates.length === 0 ? (
            <EmptyState
              icon="sparkles"
              title="Siap Mengekstrak Istilah"
              description="Pilih dokumen di atas dan klik 'Ekstrak AI' untuk menemukan definisi konsep kunci dari materi Anda."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '420px', overflowY: 'auto', paddingRight: '0.25rem' }}>
              {candidates.map((c, idx) => (
                <div
                  key={idx}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: '1rem',
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
                      <span style={{ fontWeight: '700', fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                        {c.term}
                      </span>
                      <Badge variant="secondary" size="sm">
                        {c.source || 'Dokumen'}
                      </Badge>
                      {c.page ? <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Hal. {c.page}</span> : null}
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                      {c.definition}
                    </p>
                  </div>
                  <Button variant="secondary" size="sm" icon="plus" onClick={() => handlePromoteCandidate(c)}>
                    Promosikan
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={!!deleteTarget}
        title="Hapus Istilah Glosarium"
        description={`Apakah Anda yakin ingin menghapus istilah '${deleteTarget?.term}' dari kamus?`}
        confirmText="Hapus Istilah"
        variant="danger"
        loading={deleting}
        onConfirm={handleDeleteTerm}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
