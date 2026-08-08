import { useCallback, useEffect, useState } from 'react'
import {
  api,
  type AnnotationItem,
  type CategoryInfo,
  type DocumentInfo,
  type RepeatedQuestion,
  type ReviewCard,
  type WeakSpot,
} from '../api'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Icon } from '../components/Icon'
import { usePageHeader } from '../components/PageHeader'
import { PromptDialog } from '../components/PromptDialog'
import { useToast } from '../components/Toast'
import { UploadDialog } from '../components/UploadDialog'

interface Chunk {
  chunk_index: number
  page: number
  heading: string
  text: string
}

/** Halaman /library — Manajemen dokumen & Pusat Belajar. */
export default function Library() {
  const toast = useToast()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [categories, setCategories] = useState<CategoryInfo[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string>('')
  const [search, setSearch] = useState('')
  const [cards, setCards] = useState<ReviewCard[]>([])
  const [dueToday, setDueToday] = useState(0)
  const [repeated, setRepeated] = useState<RepeatedQuestion[]>([])
  const [usage, setUsage] = useState('')
  const [weak, setWeak] = useState<WeakSpot[]>([])
  const [notes, setNotes] = useState<AnnotationItem[]>([])
  const [uploadOpen, setUploadOpen] = useState(false)
  const [ready, setReady] = useState(false)

  // Detail dokumen & chunk loading
  const [selected, setSelected] = useState<string | null>(null)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [loadingChunks, setLoadingChunks] = useState(false)
  const [annotations, setAnnotations] = useState<Record<string, string>>({})
  const [chunkFilter, setChunkFilter] = useState('')

  // State untuk custom modal
  const [deleteDocSource, setDeleteDocSource] = useState<string | null>(null)
  const [deletingDocLoading, setDeletingDocLoading] = useState(false)

  const [editCategoryDoc, setEditCategoryDoc] = useState<string | null>(null)
  const [editCategoryName, setEditCategoryName] = useState('')
  const [editingCategoryLoading, setEditingCategoryLoading] = useState(false)

  const [annotateKey, setAnnotateKey] = useState<string | null>(null)
  const [annotateNote, setAnnotateNote] = useState('')
  const [annotateLoading, setAnnotateLoading] = useState(false)

  const [answeringCardId, setAnsweringCardId] = useState<string | null>(null)

  usePageHeader({
    eyebrow: 'KNOWLEDGE BASE',
    title: 'Library Dokumen & Pembelajaran',
    actions: (
      <button className="button button-primary" type="button" onClick={() => setUploadOpen(true)}>
        <Icon name="i-upload" /> Tambah Dokumen
      </button>
    ),
  })

  const loadAll = useCallback(async () => {
    try {
      const [docs, cats, due, rep, spots, ann] = await Promise.all([
        api<{ documents: DocumentInfo[] }>('/documents'),
        api<{ categories: CategoryInfo[] }>('/categories'),
        api<{ cards: ReviewCard[]; stats: { due_today: number } }>('/learning/due'),
        api<{ questions: RepeatedQuestion[]; usage: { sessions_active: number; questions: number }; days: number }>(
          '/repeated-questions',
        ),
        api<{ weak_spots: WeakSpot[] }>('/learning/weak-spots'),
        api<{ annotations: AnnotationItem[] }>('/annotations'),
      ])
      setDocuments(docs.documents)
      setCategories(cats.categories || [])
      setCards(due.cards)
      setDueToday(due.stats.due_today)
      setRepeated(rep.questions)
      setUsage(
        `${rep.days} hari aktif · ${rep.usage.sessions_active} sesi · ${rep.usage.questions} pertanyaan`,
      )
      setWeak(spots.weak_spots)
      setNotes(ann.annotations)
      setAnnotations(Object.fromEntries(ann.annotations.map((a) => [a.chunk_key, a.note])))
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal memuat data library.')
    } finally {
      setReady(true)
    }
  }, [toast])

  useEffect(() => {
    void loadAll()
  }, [loadAll])

  async function openDocument(source: string) {
    setSelected(source)
    setChunkFilter('')
    setLoadingChunks(true)
    try {
      const data = await api<{ chunks: Chunk[] }>(`/documents/${encodeURIComponent(source)}/chunks`)
      setChunks(data.chunks || [])
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal memuat isi dokumen.')
      setChunks([])
    } finally {
      setLoadingChunks(false)
    }
  }

  // Modal custom hapus dokumen
  function promptDeleteDoc(source: string) {
    setDeleteDocSource(source)
  }

  async function handleConfirmDeleteDoc() {
    if (!deleteDocSource) return
    setDeletingDocLoading(true)
    try {
      await api(`/documents/${encodeURIComponent(deleteDocSource)}`, { method: 'DELETE' })
      toast(`Dokumen "${deleteDocSource}" berhasil dihapus.`)
      if (selected === deleteDocSource) setSelected(null)
      setDeleteDocSource(null)
      void loadAll()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menghapus dokumen.')
    } finally {
      setDeletingDocLoading(false)
    }
  }

  // Modal custom edit kategori
  function promptEditCategory(source: string, currentCategory = 'Umum') {
    setEditCategoryDoc(source)
    setEditCategoryName(currentCategory)
  }

  async function handleConfirmEditCategory(newCategory: string) {
    if (!editCategoryDoc) return
    setEditingCategoryLoading(true)
    try {
      const cat = newCategory.trim() || 'Umum'
      await api(`/documents/${encodeURIComponent(editCategoryDoc)}/category`, {
        method: 'PUT',
        body: JSON.stringify({ category: cat }),
      })
      toast(`Kategori "${editCategoryDoc}" diubah menjadi "${cat}".`)
      setEditCategoryDoc(null)
      void loadAll()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal mengubah kategori.')
    } finally {
      setEditingCategoryLoading(false)
    }
  }

  // Modal custom anotasi chunk
  function promptAnnotate(key: string, currentNote: string) {
    setAnnotateKey(key)
    setAnnotateNote(currentNote)
  }

  async function handleConfirmAnnotation(newNote: string) {
    if (!annotateKey) return
    setAnnotateLoading(true)
    try {
      if (newNote.trim()) {
        await api(`/annotations/${encodeURIComponent(annotateKey)}`, {
          method: 'PUT',
          body: JSON.stringify({ note: newNote.trim() }),
        })
      } else {
        await api(`/annotations/${encodeURIComponent(annotateKey)}`, { method: 'DELETE' })
      }
      toast(newNote.trim() ? 'Catatan disimpan.' : 'Catatan dihapus.')
      setAnnotateKey(null)
      void loadAll()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menyimpan catatan.')
    } finally {
      setAnnotateLoading(false)
    }
  }

  async function answerCard(cardId: string, remembered: boolean) {
    setAnsweringCardId(cardId)
    try {
      await api('/learning/answer', {
        method: 'POST',
        body: JSON.stringify({ card_id: cardId, remembered }),
      })
      toast(remembered ? 'Kartu ditandai Ingat' : 'Kartu akan diulang nanti')
      void loadAll()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menyimpan jawaban.')
    } finally {
      setAnsweringCardId(null)
    }
  }

  const totalChunks = documents.reduce((acc, d) => acc + d.chunks, 0)

  const filteredDocs = documents.filter((d) => {
    const matchSearch = d.source.toLowerCase().includes(search.toLowerCase())
    const matchCat = !selectedCategory || (d.category || 'Umum') === selectedCategory
    return matchSearch && matchCat
  })

  const filteredChunks = chunks.filter(
    (c) =>
      !chunkFilter ||
      c.heading.toLowerCase().includes(chunkFilter.toLowerCase()) ||
      c.text.toLowerCase().includes(chunkFilter.toLowerCase()),
  )

  const getDocExt = (name: string) => {
    const ext = name.split('.').pop()?.toUpperCase() || 'DOC'
    return ext.length <= 4 ? ext : 'DOC'
  }

  return (
    <div className="page-content">
      {/* Stat KPI Banner */}
      <div className="stat-banner">
        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-file" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{documents.length}</span>
            <span className="stat-label">Dokumen Terindeks</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-search" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{totalChunks}</span>
            <span className="stat-label">Total Chunk Materi</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-card" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{dueToday}</span>
            <span className="stat-label">Kartu Review Due Today</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-note" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{notes.length}</span>
            <span className="stat-label">Catatan & Anotasi</span>
          </div>
        </div>
      </div>

      {/* Grid Utama Library & Hub Pembelajaran */}
      <div className="library-grid">
        {/* Kolom Kiri: Manajemen Dokumen */}
        <section className="library-card library-docs" aria-labelledby="lib-docs-label">
          <div className="section-label-row">
            <h2 id="lib-docs-label">Koleksi Dokumen</h2>
            <span className="badge">{filteredDocs.length} / {documents.length}</span>
          </div>

          <div style={{ marginBottom: 'var(--space-3)' }}>
            <input
              type="text"
              className="chunk-search"
              placeholder="Cari dokumen..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          {/* Category Filter Pills */}
          {categories.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
              <button
                type="button"
                className={`button button-secondary${selectedCategory === '' ? ' is-active' : ''}`}
                style={{ minHeight: '28px', padding: '0 0.5rem', fontSize: 'var(--text-xs)', borderRadius: 'var(--radius-pill)' }}
                onClick={() => setSelectedCategory('')}
              >
                Semua ({documents.length})
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.category}
                  type="button"
                  className={`button button-secondary${selectedCategory === cat.category ? ' is-active' : ''}`}
                  style={{ minHeight: '28px', padding: '0 0.5rem', fontSize: 'var(--text-xs)', borderRadius: 'var(--radius-pill)' }}
                  onClick={() => setSelectedCategory(cat.category)}
                >
                  {cat.category} ({cat.doc_count})
                </button>
              ))}
            </div>
          )}

          <p className="watch-note" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <Icon name="i-bulb" /> Auto-index: letakkan file di <code>uploads/</code> atau subfolder kategori!
          </p>

          <div className="document-list">
            {!ready ? (
              <p className="empty-list">Memuat daftar dokumen…</p>
            ) : filteredDocs.length === 0 ? (
              <p className="empty-list">{search || selectedCategory ? 'Tidak ada dokumen yang cocok.' : 'Belum ada dokumen terindeks.'}</p>
            ) : (
              filteredDocs.map((doc) => {
                const isActive = selected === doc.source
                return (
                  <div className={`document-row${isActive ? ' is-active' : ''}`} key={doc.source}>
                    <button
                      className="document-button"
                      type="button"
                      title={`Klik untuk pratinjau ${doc.source}`}
                      onClick={() => void openDocument(doc.source)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', width: '100%' }}>
                        <span className="badge" style={{ fontSize: '0.65rem', padding: '0.1rem 0.35rem' }}>
                          {getDocExt(doc.source)}
                        </span>
                        <span className="document-title">{doc.source}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: '0.2rem' }}>
                        <small>
                          {doc.chunks} chunk · {doc.pages.length} hal
                        </small>
                        <span className="badge" style={{ fontSize: '0.6rem', padding: '0.05rem 0.3rem', background: 'var(--color-paper-soft)', color: 'var(--color-accent)' }}>
                          {doc.category || 'Umum'}
                        </span>
                      </div>
                    </button>
                    <button
                      className="document-remove"
                      type="button"
                      aria-label={`Ubah kategori ${doc.source}`}
                      title="Ubah Kategori"
                      onClick={() => promptEditCategory(doc.source, doc.category)}
                      style={{ marginRight: '0.2rem' }}
                    >
                      <Icon name="i-edit" />
                    </button>
                    <button
                      className="document-remove"
                      type="button"
                      aria-label={`Hapus ${doc.source}`}
                      title="Hapus dari indeks"
                      onClick={() => promptDeleteDoc(doc.source)}
                    >
                      <Icon name="i-trash" />
                    </button>
                  </div>
                )
              })
            )}
          </div>
        </section>

        {/* Kolom Kanan: Pratinjau Chunk Dokumen ATAU Hub Pembelajaran */}
        {selected ? (
          <section className="library-card chunk-detail" aria-labelledby="lib-chunk-label">
            <div className="section-label-row" style={{ alignItems: 'flex-start' }}>
              <div>
                <h2 id="lib-chunk-label" style={{ wordBreak: 'break-all', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Icon name="i-file" /> {selected}
                </h2>
                <small style={{ color: 'var(--color-muted)', fontFamily: 'var(--font-mono)' }}>
                  {loadingChunks ? 'Memuat chunk…' : `Menampilkan ${filteredChunks.length} dari ${chunks.length} chunk`}
                </small>
              </div>
              <button
                className="button button-secondary"
                style={{ minHeight: '32px', padding: '0 0.6rem', fontSize: 'var(--text-xs)', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                type="button"
                onClick={() => setSelected(null)}
              >
                <Icon name="i-close" /> Tutup Pratinjau
              </button>
            </div>

            <input
              className="chunk-search"
              style={{ marginTop: 'var(--space-2)' }}
              value={chunkFilter}
              onChange={(e) => setChunkFilter(e.target.value)}
              placeholder="Cari teks atau bab dalam dokumen ini…"
            />

            <div className="chunk-list">
              {loadingChunks ? (
                <div style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                  <span className="spinner" style={{ fontSize: '1.8rem', color: 'var(--color-accent)' }} />
                  <p style={{ marginTop: 'var(--space-3)', fontSize: 'var(--text-sm)', color: 'var(--color-muted)' }}>
                    Memuat isi chunk dokumen…
                  </p>
                </div>
              ) : filteredChunks.length === 0 ? (
                <p className="empty-list">Tidak ada chunk yang cocok dengan pencarian.</p>
              ) : (
                filteredChunks.map((chunk) => {
                  const key = `${selected}#${chunk.chunk_index}`
                  const note = annotations[key]
                  return (
                    <div className="chunk-item" key={key}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                        <span className="chunk-meta">
                          Halaman {chunk.page} {chunk.heading ? `· ${chunk.heading}` : ''}
                        </span>
                        <span className="badge" style={{ fontSize: '0.65rem' }}>
                          #{chunk.chunk_index}
                        </span>
                      </div>
                      <p className="chunk-text">{chunk.text}</p>
                      {note && (
                        <p className="annotation-note" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                          <Icon name="i-pin" /> Catatan: {note}
                        </p>
                      )}
                      <div style={{ marginTop: 'var(--space-2)', display: 'flex', justifyContent: 'flex-end' }}>
                        <button className="annotation-btn" type="button" onClick={() => promptAnnotate(key, note || '')} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                          {note ? (
                            <>
                              <Icon name="i-edit" /> Edit Catatan
                            </>
                          ) : (
                            <>
                              <Icon name="i-plus" /> Tambah Catatan
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </section>
        ) : (
          <>
            {/* Panel Kartu Review */}
            <section className="library-card" aria-labelledby="lib-review-label">
              <div className="section-label-row">
                <h2 id="lib-review-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Icon name="i-card" /> Review Spaced Repetition
                </h2>
                <span className="badge">{dueToday} due</span>
              </div>
              <div className="review-list">
                {!ready ? (
                  <p className="empty-list">Memuat…</p>
                ) : cards.length === 0 ? (
                  <p className="empty-list">Tidak ada kartu yang jatuh tempo hari ini. Bagus!</p>
                ) : (
                  cards.map((card) => {
                    const isProcessing = answeringCardId === card.card_id
                    return (
                      <div className="review-item" key={card.card_id}>
                        <span className="review-question" title={card.question}>
                          {card.question}
                        </span>
                        <small style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                          {card.lapses > 0 ? (
                            <>
                              <Icon name="i-alert" /> {card.lapses}× lupa
                            </>
                          ) : (
                            `Interval: ${card.interval_days} hari`
                          )}
                        </small>
                        <div className="review-actions">
                          <button
                            className="review-btn is-ok"
                            type="button"
                            disabled={isProcessing}
                            onClick={() => void answerCard(card.card_id, true)}
                          >
                            {isProcessing ? <span className="spinner" /> : 'Ingat'}
                          </button>
                          <button
                            className="review-btn is-ko"
                            type="button"
                            disabled={isProcessing}
                            onClick={() => void answerCard(card.card_id, false)}
                          >
                            {isProcessing ? <span className="spinner" /> : 'Lupa'}
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </section>

            {/* Panel Pertanyaan Berulang */}
            <section className="library-card" aria-labelledby="lib-repeated-label">
              <div className="section-label-row">
                <h2 id="lib-repeated-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Icon name="i-flame" /> Pertanyaan Sering Diajukan
                </h2>
                <span className="badge">{repeated.length}</span>
              </div>
              {usage && <p className="repeated-usage">{usage}</p>}
              <div className="repeated-list">
                {!ready ? (
                  <p className="empty-list">Memuat…</p>
                ) : repeated.length === 0 ? (
                  <p className="empty-list">Belum ada pola pertanyaan berulang.</p>
                ) : (
                  repeated.map((item) => (
                    <div className="repeated-item" key={item.question}>
                      <span className="repeated-question" title={item.question}>
                        {item.question}
                      </span>
                      <small>{item.count}× ditanyakan</small>
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* Panel Area Lemah */}
            <section className="library-card" aria-labelledby="lib-weak-label">
              <div className="section-label-row">
                <h2 id="lib-weak-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Icon name="i-bulb" /> Area Perlu Ditingkatkan
                </h2>
                <span className="badge">{weak.length}</span>
              </div>
              <div className="weak-list">
                {!ready ? (
                  <p className="empty-list">Memuat…</p>
                ) : weak.length === 0 ? (
                  <p className="empty-list">Belum ada topik lemah yang terdeteksi.</p>
                ) : (
                  weak.slice(0, 6).map((spot) => (
                    <div className="repeated-item" key={spot.topic}>
                      <span className="repeated-question" title={spot.topic}>
                        {spot.topic}
                      </span>
                      <small style={{ color: 'var(--color-error)' }}>Skor {spot.score}</small>
                    </div>
                  ))
                )}
              </div>
            </section>

            {/* Panel Catatan */}
            <section className="library-card" aria-labelledby="lib-notes-label">
              <div className="section-label-row">
                <h2 id="lib-notes-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <Icon name="i-pin" /> Catatan & Anotasi
                </h2>
                <span className="badge">{notes.length}</span>
              </div>
              <div className="notes-list">
                {!ready ? (
                  <p className="empty-list">Memuat…</p>
                ) : notes.length === 0 ? (
                  <p className="empty-list">Belum ada catatan yang ditambahkan.</p>
                ) : (
                  notes.slice(0, 6).map((item) => (
                    <div className="repeated-item" key={item.chunk_key}>
                      <span className="repeated-question" title={item.note} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Icon name="i-pin" /> {item.note}
                      </span>
                      <small>{item.chunk_key.split('#')[0]}</small>
                    </div>
                  ))
                )}
              </div>
            </section>
          </>
        )}
      </div>

      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} onUploaded={() => void loadAll()} />

      {/* Modal Custom Hapus Dokumen */}
      <ConfirmDialog
        open={deleteDocSource !== null}
        title="Hapus Dokumen?"
        message={`Apakah Anda yakin ingin menghapus "${deleteDocSource}" dari indeks? Dokumen ini tidak akan digunakan lagi sebagai rujukan jawaban RAG.`}
        confirmText="Hapus Dokumen"
        danger
        loading={deletingDocLoading}
        onConfirm={() => void handleConfirmDeleteDoc()}
        onClose={() => setDeleteDocSource(null)}
      />

      {/* Modal Custom Edit Kategori Dokumen */}
      <PromptDialog
        open={editCategoryDoc !== null}
        title="Ubah Kategori Dokumen"
        message={`Masukkan nama kategori/folder baru untuk dokumen "${editCategoryDoc}":`}
        defaultValue={editCategoryName}
        placeholder="Contoh: Semester 1, Jaringan & Subnetting"
        confirmText="Simpan Kategori"
        loading={editingCategoryLoading}
        onConfirm={(val) => void handleConfirmEditCategory(val)}
        onClose={() => setEditCategoryDoc(null)}
      />

      {/* Modal Custom Anotasi Catatan Chunk */}
      <PromptDialog
        open={annotateKey !== null}
        title="Catatan Chunk Dokumen"
        message="Masukkan catatan pribadi untuk potongan teks ini (kosongkan jika ingin menghapus catatan):"
        defaultValue={annotateNote}
        placeholder="Contoh: Ini adalah bagian utama untuk materi ujian semester"
        confirmText="Simpan Catatan"
        multiline
        loading={annotateLoading}
        onConfirm={(val) => void handleConfirmAnnotation(val)}
        onClose={() => setAnnotateKey(null)}
      />
    </div>
  )
}
