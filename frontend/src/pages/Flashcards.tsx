import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, type DocumentInfo, type Flashcard } from '../api'
import { Icon } from '../components/Icon'
import { Markdown } from '../components/Markdown'
import { usePageHeader } from '../components/PageHeader'
import { useToast } from '../components/Toast'

interface CardStat {
  heading: string
  source: string
  known_count: number
  unknown_count: number
}

/** Halaman /flashcards — Kartu Belajar 3D dengan Spaced Repetition. */
export default function Flashcards() {
  const toast = useToast()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [source, setSource] = useState('')
  const [cards, setCards] = useState<Flashcard[]>([])
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [shuffle, setShuffle] = useState(false)
  const [stats, setStats] = useState<Record<string, CardStat>>({})
  const [loading, setLoading] = useState(false)
  const [answering, setAnswering] = useState(false)

  usePageHeader({ eyebrow: 'KARTU BELAJAR', title: 'Flashcards 3D' })

  const loadStats = useCallback(async () => {
    try {
      const data = await api<{ stats: CardStat[] }>('/learning/flashcards/stats')
      setStats(Object.fromEntries(data.stats.map((s) => [s.heading, s])))
    } catch {
      /* non-kritis */
    }
  }, [])

  useEffect(() => {
    void api<{ documents: DocumentInfo[] }>('/documents').then((d) => setDocuments(d.documents))
    void loadStats()
  }, [loadStats])

  const orderedCards = useMemo(() => {
    const list = [...cards]
    if (shuffle) {
      for (let i = list.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1))
        ;[list[i], list[j]] = [list[j]!, list[i]!]
      }
    }
    return list
  }, [cards, shuffle])

  const current = orderedCards[index]

  async function load() {
    setLoading(true)
    try {
      const data = await api<{ cards: Flashcard[] }>(
        `/learning/flashcards?source=${encodeURIComponent(source || '')}`,
      )
      setCards(data.cards || [])
      setIndex(0)
      setFlipped(false)
      void loadStats()
      toast(`Berhasil memuat ${data.cards.length} kartu belajar.`)
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal memuat kartu.')
    } finally {
      setLoading(false)
    }
  }

  async function answer(known: boolean) {
    if (!current || answering) return
    setAnswering(true)
    try {
      await api('/learning/flashcards/answer', {
        method: 'POST',
        body: JSON.stringify({ heading: current.heading, source: source || '', known }),
      })
      toast(known ? 'Kartu ditandai Sudah Tahu!' : 'Kartu ditandai Perlu Belajar Lagi')
      void loadStats()
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal menyimpan jawaban.')
    } finally {
      setAnswering(false)
    }
    setFlipped(false)
    setIndex((i) => (i + 1) % orderedCards.length)
  }

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) {
        return
      }
      if (e.code === 'Space') {
        e.preventDefault()
        setFlipped((f) => !f)
      } else if (e.code === 'ArrowLeft') {
        setIndex((i) => (i - 1 + orderedCards.length) % (orderedCards.length || 1))
        setFlipped(false)
      } else if (e.code === 'ArrowRight') {
        setIndex((i) => (i + 1) % (orderedCards.length || 1))
        setFlipped(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [orderedCards.length])

  const answered = orderedCards.filter((c) => stats[c.heading]).length
  const progress = orderedCards.length ? Math.round((answered / orderedCards.length) * 100) : 0

  const groupedDocs = useMemo(() => {
    const map: Record<string, DocumentInfo[]> = {}
    for (const doc of documents) {
      const cat = doc.category || 'Umum'
      map[cat] = map[cat] || []
      map[cat].push(doc)
    }
    return map
  }, [documents])

  return (
    <div className="page-content">
      {/* Top Filter & Control Card */}
      <section className="library-card" style={{ padding: 'var(--space-4) var(--space-5)' }}>
        <div className="quiz-setup" style={{ marginBottom: 0 }}>
          <label className="field-label" style={{ flex: 1, minWidth: '15rem', marginBottom: 0 }}>
            Pilih Dokumen Sumber Materi
            <select value={source} onChange={(e) => setSource(e.target.value)} disabled={loading || answering}>
              <option value="">Semua Dokumen Terindeks</option>
              {Object.entries(groupedDocs).map(([cat, docs]) => (
                <optgroup key={cat} label={`📂 Kategori: ${cat}`}>
                  {docs.map((doc) => (
                    <option key={doc.source} value={doc.source}>
                      {doc.source} ({doc.chunks} chunk)
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>

          <button className="button button-primary" type="button" onClick={() => void load()} disabled={loading || answering}>
            {loading ? (
              <>
                <span className="spinner" style={{ marginRight: '0.4rem' }} /> Memuat Kartu…
              </>
            ) : (
              <>
                <Icon name="i-card" /> Muat Kartu Belajar
              </>
            )}
          </button>

          <label className="field-label checkbox-inline" style={{ marginBottom: 0, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <input
              type="checkbox"
              checked={shuffle}
              disabled={loading || answering}
              onChange={(e) => {
                setShuffle(e.target.checked)
                setIndex(0)
              }}
            />
            <Icon name="i-shuffle" /> Acak Urutan Kartu
          </label>
        </div>
      </section>

      {/* Empty State */}
      {cards.length === 0 && !loading && (
        <div className="empty-state" style={{ margin: '3rem auto' }}>
          <div className="empty-icon">
            <Icon name="i-card" />
          </div>
          <h2>Flashcards Materi Pembelajaran</h2>
          <p>Pilih dokumen sumber di atas lalu klik <strong>Muat Kartu Belajar</strong> untuk memulai sesi belajar memori.</p>
        </div>
      )}

      {/* Main Flashcard Stage */}
      {current && (
        <div className="flashcard-stage" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {/* Progress Header */}
          <div className="library-card" style={{ padding: 'var(--space-3) var(--space-5)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
              <span className="stat-label">
                Kartu {index + 1} dari {orderedCards.length}
              </span>
              <span className="badge">{progress}% Sudah Dijawab</span>
            </div>
            <div className="progress-track" style={{ height: '0.5rem' }}>
              <div className="progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {/* Flashcard Stats & Badge */}
          <div style={{ display: 'flex', justifyContent: 'between', alignItems: 'center', maxWidth: '38rem', margin: '0 auto', width: '100%' }}>
            <span className="badge" style={{ background: 'var(--color-paper-soft)', border: '1px solid var(--color-rule)' }}>
              {source || 'Semua Dokumen'}
            </span>
            <span className="flashcard-counter" style={{ marginLeft: 'auto' }}>
              {stats[current.heading]?.known_count || 0}× Tahu · {stats[current.heading]?.unknown_count || 0}× Belum
            </span>
          </div>

          {/* 3D Flip Card Component */}
          <div className="flashcard-perspective">
            <button
              className={`flashcard-3d${flipped ? ' is-flipped' : ''}`}
              type="button"
              onClick={() => setFlipped((v) => !v)}
              aria-label="Balik kartu"
            >
              {/* Front Face */}
              <div className="flashcard-face front">
                <span className="badge" style={{ marginBottom: 'var(--space-3)', fontSize: '0.7rem' }}>
                  PERTANYAAN / TOPIC
                </span>
                <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 800, color: 'var(--color-ink)', margin: 0 }}>
                  {current.heading}
                </h3>
                <div className="flashcard-hint">
                  <Icon name="i-zap" /> Klik atau tekan <strong>Spasi</strong> untuk melihat jawaban
                </div>
              </div>

              {/* Back Face */}
              <div className="flashcard-face back">
                <span className="badge" style={{ marginBottom: 'var(--space-3)', fontSize: '0.7rem', background: 'var(--color-accent-glow)', color: 'var(--color-accent)' }}>
                  PENJELASAN / RINGKASAN
                </span>
                <div style={{ textAlign: 'left', width: '100%', maxHeight: '10rem', overflowY: 'auto' }}>
                  <Markdown content={current.content || ''} />
                </div>
                <div className="flashcard-hint">
                  <Icon name="i-zap" /> Klik untuk balik ke depan
                </div>
              </div>
            </button>
          </div>

          {/* Navigation Controls */}
          <div className="flashcard-nav" style={{ justifyContent: 'center' }}>
            <button
              className="button button-secondary"
              type="button"
              disabled={answering}
              onClick={() => {
                setIndex((i) => (i - 1 + orderedCards.length) % orderedCards.length)
                setFlipped(false)
              }}
            >
              ‹ Kartu Sebelumnya
            </button>
            <button
              className="button button-secondary"
              type="button"
              disabled={answering}
              onClick={() => {
                setIndex((i) => (i + 1) % orderedCards.length)
                setFlipped(false)
              }}
            >
              Kartu Berikutnya ›
            </button>
          </div>

          {/* Mastery Evaluation Controls */}
          <div className="flashcard-nav" style={{ justifyContent: 'center', gap: 'var(--space-4)', marginTop: 'var(--space-2)' }}>
            <button
              className="button"
              type="button"
              disabled={answering}
              onClick={() => void answer(false)}
              style={{
                background: 'var(--color-error-bg)',
                color: 'var(--color-error)',
                border: '1px solid var(--color-error)',
                minWidth: '10rem',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.4rem',
              }}
            >
              {answering ? <span className="spinner" /> : <Icon name="i-close" />}
              <span>Belum Tahu</span>
            </button>
            <button
              className="button"
              type="button"
              disabled={answering}
              onClick={() => void answer(true)}
              style={{
                background: 'var(--color-success-bg)',
                color: 'var(--color-success)',
                border: '1px solid var(--color-success)',
                minWidth: '10rem',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.4rem',
              }}
            >
              {answering ? <span className="spinner" /> : <Icon name="i-check" />}
              <span>Sudah Tahu</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
