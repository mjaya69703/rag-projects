import React, { useEffect, useState } from 'react'
import { Button, Icon, Input, Modal, Tabs } from '../shared/components'
import { useToast } from '../shared/hooks'
import { documentService } from '../shared/services'

interface Props {
  open: boolean
  onClose: () => void
  onUploaded: () => void
}

export function UploadDialog({ open, onClose, onUploaded }: Props) {
  const { addToast } = useToast()
  const [tab, setTab] = useState<'file' | 'url'>('file')

  // File State
  const [file, setFile] = useState<File | null>(null)
  const [fileCategory, setFileCategory] = useState('Umum')
  const [uploading, setUploading] = useState(false)

  // URL State
  const [url, setUrl] = useState('')
  const [urlCategory, setUrlCategory] = useState('Umum')
  const [fetching, setFetching] = useState(false)

  if (!open) return null

  const handleFileUpload = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) {
      addToast('Pilih file dokumen terlebih dahulu.', 'warning')
      return
    }

    setUploading(true)
    try {
      await documentService.uploadFile(file, file.name, fileCategory.trim() || 'Umum')
      addToast(`Dokumen '${file.name}' berhasil diunggah dan diindeks!`, 'success')
      setFile(null)
      onUploaded()
      onClose()
    } catch (err: any) {
      addToast(err.message || 'Gagal mengunggah file.', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleUrlIngest = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url.trim()) {
      addToast('Masukkan URL target terlebih dahulu.', 'warning')
      return
    }

    setFetching(true)
    try {
      await documentService.ingestUrl(url.trim(), undefined, urlCategory.trim() || 'Umum')
      addToast('Tautan web berhasil dijadwalkan untuk ingestion!', 'success')
      setUrl('')
      onUploaded()
      onClose()
    } catch (err: any) {
      addToast(err.message || 'Gagal memproses URL.', 'error')
    } finally {
      setFetching(false)
    }
  }

  return (
    <Modal
      isOpen={open}
      onClose={onClose}
      title="Tambah Dokumen ke Knowledge Base"
      subtitle="Unggah dokumen lokal atau indeks halaman dari URL web secara aman."
      size="md"
    >
      <div style={{ marginBottom: '1.25rem' }}>
        <Tabs
          tabs={[
            { id: 'file', label: 'Unggah Berkas Lokal', icon: 'file' },
            { id: 'url', label: 'Tautan Web (URL)', icon: 'link' },
          ]}
          activeTab={tab}
          onChange={(t) => setTab(t as 'file' | 'url')}
        />
      </div>

      {tab === 'file' ? (
        <form onSubmit={handleFileUpload} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: '700', color: 'var(--text-secondary)', marginBottom: '0.35rem', textTransform: 'uppercase' }}>
              Pilih Dokumen
            </label>
            <input
              type="file"
              accept=".pdf,.md,.txt,.docx,.pptx,.html"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="form-input"
            />
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              Format didukung: PDF, Markdown, DOCX, PPTX, HTML, TXT (Maks. 50MB)
            </div>
          </div>

          <Input
            label="Kategori Materi"
            placeholder="Contoh: Jaringan, Cloud, AI, Umum"
            value={fileCategory}
            onChange={(e) => setFileCategory(e.target.value)}
          />

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <Button variant="ghost" type="button" onClick={onClose}>
              Batal
            </Button>
            <Button variant="primary" type="submit" icon="upload" loading={uploading} disabled={!file}>
              Mulai Ingestion
            </Button>
          </div>
        </form>
      ) : (
        <form onSubmit={handleUrlIngest} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="URL Web Target"
            placeholder="https://docs.python.org/3/tutorial/"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            autoFocus
          />

          <Input
            label="Kategori Materi"
            placeholder="Contoh: Python, Dokumentasi, Umum"
            value={urlCategory}
            onChange={(e) => setUrlCategory(e.target.value)}
          />

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '0.5rem' }}>
            <Button variant="ghost" type="button" onClick={onClose}>
              Batal
            </Button>
            <Button variant="primary" type="submit" icon="link" loading={fetching} disabled={!url.trim()}>
              Proses URL
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
