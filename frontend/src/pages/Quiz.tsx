import { useCallback, useEffect, useState } from 'react'
import { api, type DocumentInfo, type QuizHistoryItem, type QuizQuestion } from '../api'
import { Icon } from '../components/Icon'
import { usePageHeader } from '../components/PageHeader'
import { useToast } from '../components/Toast'

interface GradeDetail {
  correct: boolean
  correct_index: number
  explanation: string
}

const OPTION_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

/** Halaman /quiz — Latihan Soal Interaktif. */
export default function Quiz() {
  const toast = useToast()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [source, setSource] = useState('')
  const [count, setCount] = useState(5)
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [details, setDetails] = useState<GradeDetail[] | null>(null)
  const [feedback, setFeedback] = useState('')
  const [history, setHistory] = useState<QuizHistoryItem[]>([])
  const [loading, setLoading] = useState(false)
  const [grading, setGrading] = useState(false)

  usePageHeader({
    eyebrow: 'LATIHAN SOAL & EVALUASI',
    title: 'Quiz Interaktif',
    actions: (
      <button
        className="button button-primary"
        type="button"
        disabled={loading || grading || questions.length === 0}
        onClick={() => void grade()}
      >
        {grading ? (
          <>
            <span className="spinner" style={{ marginRight: '0.4rem' }} /> Memeriksa…
          </>
        ) : (
          <>
            <Icon name="i-quiz" /> Koreksi Jawaban
          </>
        )}
      </button>
    ),
  })

  const loadHistory = useCallback(async () => {
    try {
      const data = await api<{ history: QuizHistoryItem[] }>('/learning/quiz/history')
      setHistory(data.history || [])
    } catch {
      /* non-kritis */
    }
  }, [])

  useEffect(() => {
    void api<{ documents: DocumentInfo[] }>('/documents').then((d) => setDocuments(d.documents))
    void loadHistory()
  }, [loadHistory])

  async function generate() {
    const n = Math.max(1, Math.min(20, Number(count) || 5))
    setCount(n)
    setLoading(true)
    setDetails(null)
    setFeedback('')
    try {
      const data = await api<{ questions: QuizQuestion[] }>('/learning/quiz/generate', {
        method: 'POST',
        body: JSON.stringify({ source: source || null, n }),
      })
      setQuestions(data.questions || [])
      setAnswers({})
      toast(`Berhasil membuat ${data.questions.length} soal latihan. Selamat mengerjakan!`)
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal membuat soal.')
      setQuestions([])
    } finally {
      setLoading(false)
    }
  }

  async function grade() {
    if (questions.length === 0 || grading) return
    const selected = questions.map((_, i) => answers[i] ?? -1)
    if (selected.some((a) => a < 0)) {
      toast('Harap dijawab semua soal terlebih dahulu sebelum dikoreksi.')
      return
    }
    setGrading(true)
    try {
      const data = await api<{ score: number; total: number; feedback: string; details: GradeDetail[] }>(
        '/learning/quiz/grade',
        { method: 'POST', body: JSON.stringify({ questions, answers: selected }) },
      )
      setDetails(data.details || [])
      setFeedback(data.feedback)
      void loadHistory()
      toast(`Koreksi selesai! Skor Anda: ${data.score}/${data.total}`)
    } catch (error) {
      toast(error instanceof Error ? error.message : 'Gagal melakukan koreksi.')
    } finally {
      setGrading(false)
    }
  }

  const score = details ? details.filter((d) => d.correct).length : 0
  const answeredCount = Object.keys(answers).length
  const progressPercent = questions.length ? Math.round((answeredCount / questions.length) * 100) : 0

  return (
    <div className="page-content">
      {/* Quiz Setup Header Banner */}
      <section className="library-card" style={{ padding: 'var(--space-5)' }}>
        <div style={{ marginBottom: 'var(--space-3)' }}>
          <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 800, marginBottom: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Icon name="i-quiz" /> Buat Paket Soal Latihan Baru
          </h2>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)' }}>
            Pilih dokumen materi dan jumlah soal yang ingin Anda uji. Sistem RAG akan menyusun soal pilihan ganda secara relevan.
          </p>
        </div>

        <div className="quiz-setup" style={{ marginBottom: 0 }}>
          <label className="field-label" style={{ flex: 1, minWidth: '15rem', marginBottom: 0 }}>
            Dokumen Sumber Materi
            <select value={source} onChange={(e) => setSource(e.target.value)} disabled={loading || grading}>
              <option value="">Semua Dokumen Terindeks</option>
              {documents.map((doc) => (
                <option key={doc.source} value={doc.source}>
                  {doc.source} ({doc.chunks} chunk)
                </option>
              ))}
            </select>
          </label>

          <label className="field-label" style={{ width: '10rem', marginBottom: 0 }}>
            Jumlah Soal (1–20)
            <input
              type="number"
              min={1}
              max={20}
              value={count}
              disabled={loading || grading}
              onChange={(e) => setCount(Number(e.target.value))}
            />
          </label>

          <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
            {[5, 10, 15].map((n) => (
              <button
                key={n}
                type="button"
                className={`button button-secondary${count === n ? ' is-active' : ''}`}
                style={{ minHeight: '38px', padding: '0 0.6rem', fontSize: 'var(--text-xs)' }}
                disabled={loading || grading}
                onClick={() => setCount(n)}
              >
                {n} Soal
              </button>
            ))}
          </div>

          <button
            className="button button-primary"
            type="button"
            onClick={() => void generate()}
            disabled={loading || grading}
            style={{ minHeight: '40px' }}
          >
            {loading ? (
              <>
                <span className="spinner" style={{ marginRight: '0.4rem' }} /> Membuat Soal…
              </>
            ) : (
              <>
                <Icon name="i-zap" /> Generate Quiz
              </>
            )}
          </button>
        </div>
      </section>

      {/* State belum ada soal */}
      {questions.length === 0 && !loading && (
        <div className="empty-state" style={{ margin: '3rem auto' }}>
          <div className="empty-icon">
            <Icon name="i-quiz" />
          </div>
          <h2>Siap Menguji Pemahaman Anda?</h2>
          <p>Pilih dokumen sumber materi di atas lalu klik <strong>Generate Quiz</strong> untuk mulai mengerjakan latihan soal.</p>
        </div>
      )}

      {/* State Loading Pembuatan Soal */}
      {loading && questions.length === 0 && (
        <div className="library-card" style={{ padding: 'var(--space-8)', textAlign: 'center' }}>
          <span className="spinner" style={{ fontSize: '2rem', color: 'var(--color-accent)', marginBottom: 'var(--space-3)' }} />
          <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 700, margin: 0 }}>
            AI Sedang Menyusun Paket Soal Latihan…
          </h3>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginTop: '0.4rem' }}>
            Mengambil chunk dokumen relevan dan menggenerate pertanyaan pilihan ganda.
          </p>
        </div>
      )}

      {/* Quiz Questions List */}
      {questions.length > 0 && (
        <>
          {/* Progress Header Bar */}
          <div
            className="library-card"
            style={{
              padding: 'var(--space-3) var(--space-4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
              <span className="badge">
                {answeredCount}/{questions.length} Dijawab
              </span>
              <div className="progress-track" style={{ width: '12rem', height: '0.5rem' }}>
                <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>

            <button
              className="button button-primary"
              type="button"
              disabled={loading || grading || answeredCount < questions.length}
              onClick={() => void grade()}
            >
              {grading ? (
                <>
                  <span className="spinner" style={{ marginRight: '0.4rem' }} /> Memeriksa Jawaban…
                </>
              ) : (
                'Koreksi Jawaban Sekarang'
              )}
            </button>
          </div>

          {/* Banner Indikator Loading Koreksi */}
          {grading && (
            <div className="library-card" style={{ padding: 'var(--space-5)', textAlign: 'center', background: 'var(--color-paper-soft)', border: '1px solid var(--color-accent)' }}>
              <span className="spinner" style={{ fontSize: '1.8rem', color: 'var(--color-accent)', marginBottom: '0.4rem' }} />
              <h3 style={{ fontSize: 'var(--text-base)', fontWeight: 800, margin: 0, color: 'var(--color-ink)' }}>
                Sedang Mengevaluasi & Mengoreksi Jawaban Anda…
              </h3>
              <p style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)', marginTop: '0.3rem', marginBottom: 0 }}>
                LLM sedang memeriksa pilihan Anda dan membuat penjelasan lengkap. Mohon tunggu sebentar.
              </p>
            </div>
          )}

          {/* Question Cards */}
          {questions.map((q, qi) => {
            const detail = details?.[qi]
            const selected = answers[qi]
            return (
              <div
                className={`quiz-question${detail ? (detail.correct ? ' is-correct' : ' is-wrong') : ''}`}
                key={qi}
                style={{ padding: 'var(--space-5)', borderRadius: 'var(--radius-lg)' }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 'var(--space-3)', marginBottom: 'var(--space-3)' }}>
                  <p style={{ fontSize: 'var(--text-base)', fontWeight: 700, margin: 0 }}>
                    <span style={{ color: 'var(--color-accent)', marginRight: '0.4rem' }}>Soal #{qi + 1}.</span>
                    {q.question}
                  </p>
                  {detail && (
                    <span
                      className={`badge ${detail.correct ? 'badge-priority-medium' : 'badge-priority-high'}`}
                      style={{ flexShrink: 0, padding: '0.2rem 0.6rem', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
                    >
                      {detail.correct ? (
                        <>
                          <Icon name="i-check" /> Benar
                        </>
                      ) : (
                        <>
                          <Icon name="i-close" /> Salah
                        </>
                      )}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
                  {q.options.map((opt, oi) => {
                    const isSelected = selected === oi
                    const isKey = detail && oi === detail.correct_index
                    const letter = OPTION_LETTERS[oi] || `${oi + 1}`
                    return (
                      <label
                        className={`quiz-option${isSelected ? ' is-selected' : ''}${isKey ? ' is-key' : ''}${detail || grading ? ' disabled' : ''}`}
                        key={oi}
                      >
                        <input
                          type="radio"
                          name={`quiz-q${qi}`}
                          disabled={!!detail || grading}
                          checked={isSelected}
                          onChange={() => setAnswers((prev) => ({ ...prev, [qi]: oi }))}
                          style={{ display: 'none' }}
                        />
                        <span className="quiz-option-letter">{letter}</span>
                        <span style={{ flex: 1, fontSize: 'var(--text-sm)' }}>{opt}</span>
                        {isKey && (
                          <small className="quiz-key-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                            <Icon name="i-check" /> Kunci Jawaban
                          </small>
                        )}
                        {!isKey && isSelected && detail && !detail.correct && (
                          <small style={{ color: 'var(--color-error)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.2rem' }}>
                            <Icon name="i-close" /> Jawaban Anda
                          </small>
                        )}
                      </label>
                    )
                  })}
                </div>

                {detail?.explanation && (
                  <div className="quiz-explanation" style={{ marginTop: 'var(--space-3)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', background: 'var(--color-paper-soft)' }}>
                    <p style={{ margin: 0, fontWeight: 700, fontSize: 'var(--text-xs)', color: 'var(--color-secondary)', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                      <Icon name="i-bulb" /> Penjelasan:
                    </p>
                    <p style={{ margin: '0.2rem 0 0', fontSize: 'var(--text-xs)', color: 'var(--color-ink)' }}>
                      {detail.explanation}
                    </p>
                  </div>
                )}
              </div>
            )
          })}
        </>
      )}

      {/* Grade Result Banner */}
      {details && (
        <div
          className={`quiz-result${score === details.length ? ' is-perfect' : ''}`}
          style={{ padding: 'var(--space-5)', borderRadius: 'var(--radius-lg)', textAlign: 'center' }}
        >
          <h3 style={{ fontSize: 'var(--text-lg)', margin: '0 0 0.4rem', color: score === details.length ? 'var(--color-success)' : 'var(--color-ink)' }}>
            Hasil Quiz: {score} / {details.length} Benar ({Math.round((score / details.length) * 100)}%)
          </h3>
          {feedback && <p style={{ margin: 0, fontSize: 'var(--text-sm)', opacity: 0.9 }}>{feedback}</p>}
        </div>
      )}

      {/* History Quiz Section */}
      {history.length > 0 && (
        <div className="library-card" style={{ marginTop: 'var(--space-4)', padding: 'var(--space-5)' }}>
          <div className="section-label-row">
            <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Icon name="i-history" /> Riwayat Quiz Sebelumnya
            </h2>
            <span className="badge">{history.length} percobaan</span>
          </div>
          <div className="repeated-list" style={{ maxHeight: '16rem' }}>
            {history.slice(0, 10).map((item, i) => {
              const pct = Math.round((item.score / item.total) * 100)
              return (
                <div className="repeated-item" key={i} style={{ padding: '0.55rem 0.75rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
                    <span className={`badge ${pct >= 70 ? 'badge-priority-medium' : 'badge-priority-high'}`}>
                      {pct}%
                    </span>
                    <span className="repeated-question">
                      {item.source || 'Semua Dokumen'} — {item.score}/{item.total} Benar
                    </span>
                  </div>
                  <small style={{ color: 'var(--color-subtle)' }}>{(item.created_at || '').slice(0, 10)}</small>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
