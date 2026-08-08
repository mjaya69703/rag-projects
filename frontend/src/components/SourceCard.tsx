import { useMemo, useState } from 'react'
import { api, type SourceRef } from '../api'
import { Icon } from './Icon'
import { PromptDialog } from './PromptDialog'
import { useToast } from './Toast'

interface Props {
  sources: SourceRef[]
  annotations: Record<string, string>
  onAnnotated: () => void
}

function chunkKey(source: SourceRef) {
  return `${source.source}#${source.chunk_index ?? 0}`
}

/** Sumber rujukan: accordion per jawaban + catatan pribadi (fitur #9). */
export function SourceAccordion({ sources, annotations, onAnnotated }: Props) {
  const toast = useToast()
  const [open, setOpen] = useState(false)

  // State untuk prompt dialog kustom
  const [activeSource, setActiveSource] = useState<SourceRef | null>(null)
  const [loading, setLoading] = useState(false)

  function openPrompt(source: SourceRef) {
    setActiveSource(source)
  }

  async function handleConfirm(noteText: string) {
    if (!activeSource) return
    const key = chunkKey(activeSource)
    setLoading(true)
    try {
      if (noteText.trim()) {
        await api(`/annotations/${encodeURIComponent(key)}`, {
          method: 'PUT',
          body: JSON.stringify({ note: noteText.trim() }),
        })
      } else {
        await api(`/annotations/${encodeURIComponent(key)}`, { method: 'DELETE' })
      }
      toast(noteText.trim() ? 'Catatan disalin ke chunk.' : 'Catatan dihapus.')
      setActiveSource(null)
      onAnnotated()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menyimpan catatan.')
    } finally {
      setLoading(false)
    }
  }

  const currentNote = activeSource ? annotations[chunkKey(activeSource)] || '' : ''

  return (
    <>
      <details className="source-accordion" open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
        <summary className="source-summary">
          <span className="source-summary-title">
            <svg className="icon" aria-hidden="true">
              <use href="#i-file" />
            </svg>
            <span>Sumber Rujukan</span>
            <span className="source-badge">{sources.length}</span>
          </span>
          <span className="source-chevron">
            <svg className="icon" aria-hidden="true">
              <use href="#i-chevron" />
            </svg>
          </span>
        </summary>
        <div className="source-list">
          {sources.map((source, i) => {
            const key = chunkKey(source)
            const note = annotations[key]
            return (
              <div className="source-card" key={`${key}-${i}`}>
                <strong>{source.heading || 'Bagian dokumen'}</strong>
                <small>
                  {source.source} · halaman {source.page}
                </small>
                <p>{(source.text || '').slice(0, 320)}</p>
                {note && (
                  <p className="annotation-note" style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <Icon name="i-pin" /> {note}
                  </p>
                )}
                <button
                  className="annotation-btn"
                  type="button"
                  onClick={() => openPrompt(source)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                >
                  {note ? (
                    <>
                      <Icon name="i-edit" /> Edit catatan
                    </>
                  ) : (
                    <>
                      <Icon name="i-plus" /> catat
                    </>
                  )}
                </button>
              </div>
            )
          })}
        </div>
      </details>

      <PromptDialog
        open={activeSource !== null}
        title="Catatan Rujukan Dokumen"
        message="Masukkan catatan pribadi untuk kutipan chunk ini (kosongkan untuk menghapus):"
        defaultValue={currentNote}
        placeholder="Contoh: Penting untuk dibaca kembali saat ujian"
        confirmText="Simpan Catatan"
        multiline
        loading={loading}
        onConfirm={(val) => void handleConfirm(val)}
        onClose={() => setActiveSource(null)}
      />
    </>
  )
}

/** Catatan cache / grounding helper — dipakai render jawaban. */
export function useAnnotationLoader() {
  const [annotations, setAnnotations] = useState<Record<string, string>>({})
  const load = useMemo(
    () => async () => {
      try {
        const data = await api<{ annotations: { chunk_key: string; note: string }[] }>('/annotations')
        setAnnotations(Object.fromEntries(data.annotations.map((a) => [a.chunk_key, a.note])))
      } catch {
        /* non-kritis */
      }
    },
    [],
  )
  return { annotations, loadAnnotations: load }
}
