import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type ProgressDoc, type QuizHistoryItem, type ReviewCard, type WeakSpot } from '../api'
import { Icon } from '../components/Icon'
import { usePageHeader } from '../components/PageHeader'
import { useToast } from '../components/Toast'

/** Halaman /progress — Analytics Dashboard & Tracking Pembelajaran. */
export default function Progress() {
  const toast = useToast()
  const [docs, setDocs] = useState<ProgressDoc[]>([])
  const [weak, setWeak] = useState<WeakSpot[]>([])
  const [due, setDue] = useState<ReviewCard[]>([])
  const [history, setHistory] = useState<QuizHistoryItem[]>([])
  const [ready, setReady] = useState(false)

  usePageHeader({ eyebrow: 'TRACKING & ANALYTICS', title: 'Progress Pembelajaran' })

  useEffect(() => {
    void (async () => {
      try {
        const [p, w, d, h] = await Promise.all([
          api<{ documents: ProgressDoc[] }>('/learning/progress'),
          api<{ weak_spots: WeakSpot[] }>('/learning/weak-spots'),
          api<{ cards: ReviewCard[] }>('/learning/due'),
          api<{ history: QuizHistoryItem[] }>('/learning/quiz/history'),
        ])
        setDocs(p.documents)
        setWeak(w.weak_spots)
        setDue(d.cards)
        setHistory(h.history || [])
      } catch (error) {
        toast(error instanceof Error ? error.message : 'Gagal memuat data progress.')
      } finally {
        setReady(true)
      }
    })()
  }, [toast])

  const totalQuestionsAsked = docs.reduce((acc, d) => acc + d.total_questions, 0)

  return (
    <div className="page-content">
      {/* Top Stat KPI Banner */}
      <div className="stat-banner">
        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-chat" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{totalQuestionsAsked}</span>
            <span className="stat-label">Total Pertanyaan Diajukan</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-file" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{docs.length}</span>
            <span className="stat-label">Dokumen Dipelajari</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-bulb" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{weak.length}</span>
            <span className="stat-label">Area Perlu Diperbaiki</span>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon-wrapper">
            <Icon name="i-card" />
          </div>
          <div className="stat-info">
            <span className="stat-value">{due.length}</span>
            <span className="stat-label">Kartu Review Due Today</span>
          </div>
        </div>
      </div>

      {/* Grid Layout Analytics */}
      <div className="library-grid">
        {/* Coverage Per Dokumen */}
        <section className="library-card library-docs" aria-labelledby="prog-docs-label">
          <div className="section-label-row">
            <h2 id="prog-docs-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Icon name="i-chart" /> Cakupan Materi Per Dokumen
            </h2>
            <span className="badge">{docs.length} dokumen</span>
          </div>
          {!ready ? (
            <p className="empty-list">Memuat…</p>
          ) : docs.length === 0 ? (
            <p className="empty-list">Belum ada data aktivitas pembelajaran.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {docs.map((doc) => {
                const subHeadings = doc.headings_covered.length
                return (
                  <div className="progress-doc" key={doc.source} style={{ padding: 'var(--space-4)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.3rem' }}>
                      <strong style={{ fontSize: 'var(--text-sm)', wordBreak: 'break-all' }}>{doc.source}</strong>
                      <span className="badge" style={{ fontSize: '0.68rem' }}>{doc.total_questions} Q</span>
                    </div>

                    <div style={{ marginBottom: 'var(--space-2)' }}>
                      <small style={{ color: 'var(--color-muted)' }}>
                        Sub-bab dibahas: {subHeadings} topik
                      </small>
                    </div>

                    <ul className="progress-headings" style={{ listStyle: 'none', paddingLeft: 0 }}>
                      {doc.headings_covered.length === 0 && (
                        <li className="empty-list">Belum ada bab spesifik yang dibahas.</li>
                      )}
                      {doc.headings_covered.map((h) => (
                        <li
                          key={h.heading}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            padding: '0.2rem 0',
                            borderBottom: '1px dashed var(--color-rule-light)',
                          }}
                        >
                          <span>• {h.heading}</span>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--color-accent)' }}>
                            {h.asked}×
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          )}
        </section>

        {/* Matrix Area Lemah */}
        <section className="library-card" aria-labelledby="prog-weak-label">
          <div className="section-label-row">
            <h2 id="prog-weak-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Icon name="i-alert" /> Area Lemah (Perlu Review)
            </h2>
            <span className="badge">{weak.length}</span>
          </div>
          {!ready ? (
            <p className="empty-list">Memuat…</p>
          ) : weak.length === 0 ? (
            <p className="empty-list">Belum ada topik lemah yang terdeteksi.</p>
          ) : (
            <div className="repeated-list">
              {weak.map((spot) => (
                <div className="repeated-item" key={spot.topic} style={{ padding: '0.55rem 0.75rem' }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.1rem', flex: 1, minWidth: 0 }}>
                    <span className="repeated-question" title={spot.topic} style={{ fontWeight: 600 }}>
                      {spot.topic}
                    </span>
                    <small style={{ color: 'var(--color-error)' }}>Tingkat Kesulitan: Skor {spot.score}</small>
                  </div>
                  <Link
                    to="/quiz"
                    className="button button-secondary"
                    style={{ minHeight: '28px', padding: '0 0.5rem', fontSize: '0.7rem' }}
                  >
                    Latih
                  </Link>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Kartu Review Due */}
        <section className="library-card" aria-labelledby="prog-due-label">
          <div className="section-label-row">
            <h2 id="prog-due-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Icon name="i-refresh" /> Antrean Kartu Review
            </h2>
            <span className="badge">{due.length} due</span>
          </div>
          {!ready ? (
            <p className="empty-list">Memuat…</p>
          ) : due.length === 0 ? (
            <p className="empty-list">Tidak ada kartu yang perlu di-review hari ini.</p>
          ) : (
            <div className="repeated-list">
              {due.map((card) => (
                <div className="repeated-item" key={card.card_id}>
                  <span className="repeated-question" title={card.question}>
                    {card.question}
                  </span>
                  <small>{card.lapses > 0 ? `${card.lapses}× lupa` : `Interval: ${card.interval_days}h`}</small>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Riwayat Quiz Timeline */}
        <section className="library-card" aria-labelledby="prog-quiz-label">
          <div className="section-label-row">
            <h2 id="prog-quiz-label" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Icon name="i-history" /> Riwayat Skor Quiz
            </h2>
            <span className="badge">{history.length}</span>
          </div>
          {!ready ? (
            <p className="empty-list">Memuat…</p>
          ) : history.length === 0 ? (
            <p className="empty-list">Belum ada riwayat pengerjaan quiz.</p>
          ) : (
            <div className="repeated-list">
              {history.slice(0, 10).map((item, i) => {
                const pct = Math.round((item.score / item.total) * 100)
                return (
                  <div className="repeated-item" key={i}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <span className={`badge ${pct >= 70 ? 'badge-priority-medium' : 'badge-priority-high'}`} style={{ fontSize: '0.65rem' }}>
                        {pct}%
                      </span>
                      <span className="repeated-question">
                        {item.source ? `${item.source}` : 'Semua Dokumen'} ({item.score}/{item.total})
                      </span>
                    </div>
                    <small>{(item.created_at || '').slice(0, 10)}</small>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
