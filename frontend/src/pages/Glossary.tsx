import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, type DocumentInfo, type GlossaryTerm } from '../api'
import { Dialog, DialogHeading } from '../components/Dialog'
import { Icon } from '../components/Icon'
import { usePageHeader } from '../components/PageHeader'
import { useToast } from '../components/Toast'

interface FormState {
  term: string
  definition: string
  source: string
  page: string
  category: string
  verified: boolean
}

interface Candidate {
  term: string
  definition: string
  source: string
  page: number | null
  category: string
  selected: boolean
}

const EMPTY_FORM: FormState = {
  term: '',
  definition: '',
  source: '',
  page: '',
  category: 'Umum',
  verified: false,
}

export default function Glossary() {
  const toast = useToast()
  const [terms, setTerms] = useState<GlossaryTerm[]>([])
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [verifiedOnly, setVerifiedOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [editing, setEditing] = useState<GlossaryTerm | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [extractOpen, setExtractOpen] = useState(false)
  const [extracting, setExtracting] = useState(false)
  const [extractPhase, setExtractPhase] = useState('Menyiapkan dokumen…')
  const [importing, setImporting] = useState(false)
  const [extractSource, setExtractSource] = useState('')
  const [extractCount, setExtractCount] = useState(10)
  const [candidates, setCandidates] = useState<Candidate[]>([])

  usePageHeader({ eyebrow: 'REFERENCE LAYER', title: 'Glossary' })

  async function loadTerms(nextSearch = search, nextVerified = verifiedOnly) {
    setLoading(true)
    try {
      const params = new URLSearchParams({ q: nextSearch, limit: '200' })
      if (nextVerified) params.set('verified', 'true')
      const data = await api<{ terms: GlossaryTerm[] }>(`/api/glossary?${params.toString()}`)
      setTerms(data.terms)
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal memuat glossary.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadTerms('', false)
    // Initial load only; searches are explicit via the form.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    void api<{ documents: DocumentInfo[] }>('/documents')
      .then((data) => setDocuments(data.documents.filter((item) => item.source)))
      .catch(() => setDocuments([]))
  }, [])

  useEffect(() => {
    if (!extracting) return
    const phases = ['Membaca chunk dokumen…', 'Menyusun kandidat istilah…', 'Menunggu jawaban AI…']
    let index = 0
    setExtractPhase(phases[0] ?? 'Membaca chunk dokumen…')
    const timer = window.setInterval(() => {
      index = (index + 1) % phases.length
      setExtractPhase(phases[index] ?? phases[0] ?? 'Membaca chunk dokumen…')
    }, 1100)
    return () => window.clearInterval(timer)
  }, [extracting])

  const categories = useMemo(() => [...new Set(terms.map((item) => item.category).filter(Boolean))], [terms])

  function openCreate() {
    setEditing(null)
    setForm(EMPTY_FORM)
    setFormOpen(true)
  }

  function openEdit(item: GlossaryTerm) {
    setEditing(item)
    setFormOpen(true)
    setForm({
      term: item.term,
      definition: item.definition,
      source: item.source,
      page: item.page ? String(item.page) : '',
      category: item.category || 'Umum',
      verified: item.verified,
    })
  }

  function closeForm() {
    if (!saving) {
      setEditing(null)
      setFormOpen(false)
    }
  }

  async function extractTerms(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (extracting) return
    setExtracting(true)
    try {
      const data = await api<{ candidates: Omit<Candidate, 'selected'>[] }>('/api/glossary/extract', {
        method: 'POST',
        body: JSON.stringify({ source: extractSource || null, n: extractCount }),
      })
      setCandidates(data.candidates.map((item) => ({ ...item, selected: true })))
      toast(data.candidates.length ? `${data.candidates.length} kandidat istilah ditemukan. Review sebelum simpan.` : 'Tidak ada istilah yang cukup jelas ditemukan.')
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal mengekstrak istilah.')
    } finally {
      setExtracting(false)
      setExtractPhase('Menyiapkan dokumen…')
    }
  }

  async function importCandidates() {
    const selected = candidates.filter((item) => item.selected)
    if (!selected.length || importing) return
    setImporting(true)
    let saved = 0
    try {
      for (const item of selected) {
        try {
          await api('/api/glossary', {
            method: 'POST',
            body: JSON.stringify({ ...item, selected: undefined, verified: false }),
          })
          saved += 1
        } catch (error) {
          // Duplicate candidates do not block the remaining imports.
          if (!(error instanceof Error && error.message.includes('sudah ada'))) throw error
        }
      }
      toast(`${saved} istilah disimpan sebagai draft. Periksa dan verifikasi sebelum digunakan.`)
      setCandidates([])
      setExtractOpen(false)
      await loadTerms()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menyimpan kandidat istilah.')
    } finally {
      setImporting(false)
    }
  }

  async function saveTerm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!form.term.trim() || !form.definition.trim() || saving) return
    setSaving(true)
    try {
      const payload = {
        term: form.term.trim(),
        definition: form.definition.trim(),
        source: form.source.trim() || null,
        page: form.page.trim() ? Number(form.page) : null,
        category: form.category.trim() || 'Umum',
        verified: form.verified,
      }
      if (editing) {
        await api(`/api/glossary/${editing.id}`, { method: 'PUT', body: JSON.stringify(payload) })
        toast(`Istilah “${payload.term}” diperbarui.`)
      } else {
        await api('/api/glossary', { method: 'POST', body: JSON.stringify(payload) })
        toast(`Istilah “${payload.term}” ditambahkan.`)
      }
      setEditing(null)
      setFormOpen(false)
      await loadTerms()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menyimpan istilah.')
    } finally {
      setSaving(false)
    }
  }

  async function removeTerm(item: GlossaryTerm) {
    if (deleting !== null) return
    setDeleting(item.id)
    try {
      await api(`/api/glossary/${item.id}`, { method: 'DELETE' })
      toast(`Istilah “${item.term}” dihapus.`)
      await loadTerms()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menghapus istilah.')
    } finally {
      setDeleting(null)
    }
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  return (
    <div className="page-content">
      <section className="library-card glossary-intro" aria-labelledby="glossary-title">
        <div className="section-label-row">
          <div>
            <p className="eyebrow">ISTILAH & DEFINISI</p>
            <h1 id="glossary-title">Glossary dokumen</h1>
          </div>
          <span className="badge">{terms.length} istilah</span>
        </div>
        <p className="glossary-lead">
          Simpan definisi yang sudah Anda pahami, lengkapi dengan sumber, lalu tandai terverifikasi agar bisa menjadi referensi belajar yang tepercaya.
        </p>
        <div className="glossary-toolbar">
          <form className="glossary-search" onSubmit={(event) => { event.preventDefault(); setSearch(query); void loadTerms(query, verifiedOnly) }}>
            <Icon name="i-search" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Cari istilah atau definisi…" aria-label="Cari glossary" />
            <button className="button button-secondary" type="submit" disabled={loading}>Cari</button>
          </form>
          <label className="glossary-check">
            <input type="checkbox" checked={verifiedOnly} onChange={(event) => { setVerifiedOnly(event.target.checked); void loadTerms(search, event.target.checked) }} />
            Hanya terverifikasi
          </label>
          <button className="button button-primary" type="button" onClick={openCreate}>
            <Icon name="i-plus" /> Tambah istilah
          </button>
          <button className="button button-secondary" type="button" onClick={() => setExtractOpen(true)}>
            <Icon name="i-sparkles" /> Ekstrak dari dokumen
          </button>
        </div>
      </section>

      <section className="glossary-list" aria-live="polite">
        {loading ? <p className="empty-list">Memuat glossary…</p> : null}
        {!loading && terms.length === 0 ? (
          <div className="library-card glossary-empty">
            <Icon name="i-mark" />
            <strong>Belum ada istilah</strong>
            <p>Tambahkan istilah pertama dari materi Anda agar pencarian dan proses belajar lebih konsisten.</p>
            <button className="button button-primary" type="button" onClick={openCreate}>Tambah istilah pertama</button>
          </div>
        ) : null}
        {!loading && terms.map((item) => (
          <article className="library-card glossary-item" key={item.id}>
            <div className="glossary-item-head">
              <div>
                <div className="glossary-term-row">
                  <h2>{item.term}</h2>
                  <span className={`badge${item.verified ? ' is-success' : ''}`}>{item.verified ? 'TERVERIFIKASI' : 'DRAFT'}</span>
                </div>
                <p className="glossary-definition">{item.definition}</p>
              </div>
              <div className="glossary-actions">
                <button className="icon-button" type="button" aria-label={`Edit ${item.term}`} title="Edit istilah" onClick={() => openEdit(item)}><Icon name="i-edit" /></button>
                <button className="icon-button danger" type="button" aria-label={`Hapus ${item.term}`} title="Hapus istilah" disabled={deleting === item.id} onClick={() => void removeTerm(item)}><Icon name="i-trash" /></button>
              </div>
            </div>
            <div className="glossary-meta">
              <span>{item.category}</span>
              {item.source ? <span>{item.source}{item.page ? ` · halaman ${item.page}` : ''}</span> : <span>Sumber belum dicatat</span>}
            </div>
          </article>
        ))}
      </section>

      <Dialog open={formOpen} onClose={closeForm}>
        <div className="modal-card glossary-form-card">
          <DialogHeading eyebrow="GLOSSARY" title={editing ? 'Edit istilah' : 'Tambah istilah'} onClose={closeForm} />
          <form onSubmit={(event) => void saveTerm(event)}>
            <label className="field-label">Istilah<input autoFocus value={form.term} onChange={(event) => update('term', event.target.value)} maxLength={160} required placeholder="Contoh: Retrieval-Augmented Generation" /></label>
            <label className="field-label">Definisi<textarea value={form.definition} onChange={(event) => update('definition', event.target.value)} maxLength={3000} required placeholder="Jelaskan arti istilah dengan bahasa yang mudah dipahami…" rows={5} /></label>
            <div className="glossary-form-grid">
              <label className="field-label">Sumber dokumen<input value={form.source} onChange={(event) => update('source', event.target.value)} placeholder="Nama file atau URL" /></label>
              <label className="field-label">Halaman<input type="number" min="1" value={form.page} onChange={(event) => update('page', event.target.value)} placeholder="Opsional" /></label>
            </div>
            <div className="glossary-form-grid">
              <label className="field-label">Kategori<input value={form.category} onChange={(event) => update('category', event.target.value)} list="glossary-categories" /></label>
              <label className="glossary-verify"><input type="checkbox" checked={form.verified} onChange={(event) => update('verified', event.target.checked)} /> Saya sudah memverifikasi definisi ini</label>
            </div>
            <datalist id="glossary-categories">{categories.map((category) => <option key={category} value={category} />)}</datalist>
            <div className="glossary-form-actions"><button className="button button-secondary" type="button" onClick={closeForm} disabled={saving}>Batal</button><button className="button button-primary" type="submit" disabled={saving || !form.term.trim() || !form.definition.trim()}>{saving ? 'Menyimpan…' : editing ? 'Simpan perubahan' : 'Simpan istilah'}</button></div>
          </form>
        </div>
      </Dialog>

      <Dialog open={extractOpen} onClose={() => { if (!extracting && !importing) setExtractOpen(false) }}>
        <div className="modal-card glossary-form-card glossary-extract-card">
          <DialogHeading eyebrow="AI ASSISTED" title="Ekstrak istilah dari dokumen" onClose={() => { if (!extracting && !importing) setExtractOpen(false) }} />
          <p className="glossary-extract-note">AI hanya mengusulkan kandidat. Kandidat akan disimpan sebagai draft dan tetap perlu Anda periksa.</p>
          <form onSubmit={(event) => void extractTerms(event)}>
            <label className="field-label">Dokumen sumber<select value={extractSource} onChange={(event) => setExtractSource(event.target.value)} disabled={extracting || importing}>
              <option value="">Semua dokumen</option>
              {documents.map((document) => <option key={document.source} value={document.source}>{document.source}</option>)}
            </select></label>
            <label className="field-label">Jumlah kandidat<input type="number" min="1" max="20" value={extractCount} onChange={(event) => setExtractCount(Number(event.target.value) || 1)} disabled={extracting || importing} /></label>
            {extracting ? <div className="glossary-progress" role="status" aria-live="polite"><div className="progress-track"><div className="progress-fill is-indeterminate" /></div><div className="glossary-progress-copy"><span>{extractPhase}</span><span>Proses AI dapat membutuhkan beberapa saat</span></div></div> : null}
            <button className="button button-primary full-width" type="submit" disabled={extracting || importing}>{extracting ? 'Menganalisis dokumen…' : 'Temukan istilah'}</button>
          </form>
          {candidates.length ? <div className="glossary-candidates">
            <div className="section-label-row"><strong>Review kandidat</strong><span className="badge">{candidates.filter((item) => item.selected).length} dipilih</span></div>
            {candidates.map((item, index) => <label className={`glossary-candidate${item.selected ? ' is-selected' : ''}`} key={`${item.term}-${index}`}>
              <input type="checkbox" checked={item.selected} onChange={(event) => setCandidates((current) => current.map((candidate, candidateIndex) => candidateIndex === index ? { ...candidate, selected: event.target.checked } : candidate))} />
              <span><strong>{item.term}</strong><small>{item.definition}</small><em>{item.source || extractSource || 'Sumber tidak diketahui'}{item.page ? ` · halaman ${item.page}` : ''}</em></span>
            </label>)}
            <button className="button button-primary full-width" type="button" onClick={() => void importCandidates()} disabled={importing || !candidates.some((item) => item.selected)}>{importing ? 'Menyimpan kandidat…' : 'Simpan kandidat terpilih sebagai draft'}</button>
          </div> : null}
        </div>
      </Dialog>
    </div>
  )
}
