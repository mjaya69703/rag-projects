import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, ApiError, type CategoryInfo } from '../api'
import { Icon } from './Icon'
import { useToast } from './Toast'

interface Props {
  open: boolean
  onClose: () => void
  onUploaded: () => void
}

/** Dialog tambah dokumen: upload file (PDF/MD/TXT) atau index dari URL. */
export function UploadDialog({ open, onClose, onUploaded }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const toast = useToast()

  const [categories, setCategories] = useState<CategoryInfo[]>([])
  const [file, setFile] = useState<File | null>(null)
  const [fileName, setFileName] = useState('')
  const [fileCategory, setFileCategory] = useState('')
  const [fileFeedback, setFileFeedback] = useState('')
  const [uploading, setUploading] = useState(false)

  const [url, setUrl] = useState('')
  const [urlName, setUrlName] = useState('')
  const [urlCategory, setUrlCategory] = useState('')
  const [urlFeedback, setUrlFeedback] = useState('')
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open) {
      if (!dialog.open) dialog.showModal()
      // Fetch daftar kategori terkini saat dialog dibuka
      void api<{ categories: CategoryInfo[] }>('/categories')
        .then((res) => setCategories(res.categories || []))
        .catch(() => setCategories([]))
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    const onCancel = (event: Event) => {
      event.preventDefault()
      onClose()
    }
    dialog.addEventListener('cancel', onCancel)
    return () => dialog.removeEventListener('cancel', onCancel)
  }, [onClose])

  async function submitFile(event: FormEvent) {
    event.preventDefault()
    if (!file) {
      setFileFeedback('Pilih file dulu.')
      return
    }
    setUploading(true)
    setFileFeedback('Mengekstrak dan mengindeks dokumen…')
    try {
      const form = new FormData()
      form.append('file', file)
      if (fileName.trim()) form.append('source', fileName.trim())
      if (fileCategory.trim()) form.append('category', fileCategory.trim())
      const data = await api<{ chunks: number; source: string; category?: string }>('/upload', { method: 'POST', body: form })
      toast(`${data.chunks} chunk dari “${data.source}” [${data.category || 'Umum'}] terindeks.`)
      onUploaded()
      onClose()
    } catch (error) {
      setFileFeedback(error instanceof Error ? error.message : 'Gagal upload.')
    } finally {
      setUploading(false)
    }
  }

  async function submitUrl(event: FormEvent) {
    event.preventDefault()
    if (!url.trim()) {
      setUrlFeedback('Masukkan URL dulu.')
      return
    }
    setFetching(true)
    setUrlFeedback('Mengambil dan mengindeks URL…')
    try {
      const data = await api<{ chunks: number; source: string; category?: string }>('/ingest-url', {
        method: 'POST',
        body: JSON.stringify({
          url: url.trim(),
          source: urlName.trim() || null,
          category: urlCategory.trim() || null,
        }),
      })
      toast(`${data.chunks} chunk dari “${data.source}” [${data.category || 'Umum'}] terindeks.`)
      setUrl('')
      setUrlName('')
      setUrlCategory('')
      onUploaded()
      onClose()
    } catch (error) {
      setUrlFeedback(error instanceof ApiError ? error.message : 'Gagal mengambil URL.')
    } finally {
      setFetching(false)
    }
  }

  return (
    <dialog ref={dialogRef} className="modal" aria-labelledby="upload-title">
      <div className="modal-card">
        <div className="modal-heading">
          <div>
            <p className="eyebrow">INGESTION DOKUMEN</p>
            <h2 id="upload-title">Tambahkan Dokumen</h2>
          </div>
          <button className="icon-button" aria-label="Tutup" onClick={onClose} disabled={uploading || fetching}>
            <Icon name="i-close" />
          </button>
        </div>

        {/* Datalist rekomendasi kategori */}
        <datalist id="category-suggestions">
          {categories.map((c) => (
            <option key={c.category} value={c.category} />
          ))}
        </datalist>

        <form onSubmit={submitFile} noValidate>
          <label className="file-drop">
            <input
              type="file"
              disabled={uploading || fetching}
              accept=".pdf,.md,.txt,.markdown,application/pdf,text/markdown,text/plain"
              onChange={(event) => {
                const f = event.target.files?.[0] ?? null
                setFile(f)
                setFileFeedback(f ? `File siap: ${f.name} (${(f.size / 1024 / 1024).toFixed(1)} MB)` : '')
              }}
            />
            <span className="file-icon">
              <Icon name="i-upload" />
            </span>
            <strong>Pilih file</strong>
            <small>PDF · MD · TXT — maksimum 50 MB</small>
          </label>
          <label className="field-label">
            Nama Sumber <span>(opsional)</span>
            <input
              maxLength={200}
              disabled={uploading || fetching}
              placeholder="Contoh: Modul Jaringan 2026"
              value={fileName}
              onChange={(event) => setFileName(event.target.value)}
            />
          </label>
          <label className="field-label">
            Kategori / Matkul <span>(opsional, default: Umum)</span>
            <input
              list="category-suggestions"
              maxLength={100}
              disabled={uploading || fetching}
              placeholder="Pilih atau ketik baru (mis. Semester 1, Jaringan)"
              value={fileCategory}
              onChange={(event) => setFileCategory(event.target.value)}
            />
          </label>
          <p className={`form-feedback${fileFeedback.startsWith('Gagal') ? ' is-error' : ''}`} aria-live="polite">
            {fileFeedback}
          </p>
          <button className="button button-primary full-width" type="submit" disabled={uploading || fetching}>
            {uploading ? <span className="spinner" style={{ marginRight: '0.4rem' }} /> : <Icon name="i-upload" />}
            <span>{uploading ? 'Mengindeks Dokumen…' : 'Index Dokumen'}</span>
          </button>
        </form>

        <div className="url-ingest-divider" aria-hidden="true">
          <span>atau dari URL</span>
        </div>

        <form className="url-ingest" onSubmit={submitUrl} noValidate>
          <label className="field-label">
            Alamat URL
            <input
              type="url"
              maxLength={2000}
              disabled={uploading || fetching}
              placeholder="https://contoh.com/artikel"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
            />
          </label>
          <label className="field-label">
            Nama Sumber <span>(opsional)</span>
            <input
              maxLength={200}
              disabled={uploading || fetching}
              placeholder="Kosong = pakai URL"
              value={urlName}
              onChange={(event) => setUrlName(event.target.value)}
            />
          </label>
          <label className="field-label">
            Kategori / Matkul <span>(opsional, default: Umum)</span>
            <input
              list="category-suggestions"
              maxLength={100}
              disabled={uploading || fetching}
              placeholder="Pilih atau ketik baru (mis. Artikel Web)"
              value={urlCategory}
              onChange={(event) => setUrlCategory(event.target.value)}
            />
          </label>
          <p className={`form-feedback${urlFeedback.startsWith('Gagal') ? ' is-error' : ''}`} aria-live="polite">
            {urlFeedback}
          </p>
          <button className="button button-secondary full-width" type="submit" disabled={uploading || fetching}>
            {fetching ? <span className="spinner" style={{ marginRight: '0.4rem' }} /> : <Icon name="i-search" />}
            <span>{fetching ? 'Mengambil URL…' : 'Index dari URL'}</span>
          </button>
        </form>
      </div>
    </dialog>
  )
}
