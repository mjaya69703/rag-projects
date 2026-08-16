import React, { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  Input,
  Modal,
  PageHeader,
  Select,
  Spinner,
  StatCard,
  Tabs,
} from '../shared/components'
import { useToast } from '../shared/hooks'
import { documentService, learningService } from '../shared/services'
import type { DocumentInfo, QuizAttempt, QuizAttemptDetail, QuizGradeResult, QuizScoreItem } from '../shared/types'

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

function accuracyBadge(pct: number): 'success' | 'warning' | 'error' {
  return pct >= 80 ? 'success' : pct >= 50 ? 'warning' : 'error'
}

export default function Quiz() {
  const { addToast } = useToast()
  const [searchParams] = useSearchParams()
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [history, setHistory] = useState<QuizScoreItem[]>([])
  const [selectedDoc, setSelectedDoc] = useState<string>('')
  const [questionCount, setQuestionCount] = useState<number>(5)
  const [quizTopic, setQuizTopic] = useState<string>(() => searchParams.get('topic') || '')
  const [activeTab, setActiveTab] = useState<'play' | 'history'>('play')

  // Active Quiz State
  const [attempt, setAttempt] = useState<QuizAttempt | null>(null)
  const [userAnswers, setUserAnswers] = useState<number[]>([])
  const [currentStep, setCurrentStep] = useState(0)
  const [generating, setGenerating] = useState(false)
  const [grading, setGrading] = useState(false)
  const [result, setResult] = useState<QuizGradeResult | null>(null)

  // History Review State
  const [reviewing, setReviewing] = useState<QuizAttemptDetail | null>(null)
  const [reviewLoadingId, setReviewLoadingId] = useState<string | null>(null)

  // Generate Modal
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false)

  useEffect(() => {
    loadInitialData()
  }, [])

  // Datang dari Progress (weak-spot) dengan ?topic= → langsung siapkan kuis
  useEffect(() => {
    if (searchParams.get('topic')) {
      setIsGenerateModalOpen(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory()
    }
  }, [activeTab])

  const loadInitialData = async () => {
    try {
      const [docsRes, histRes] = await Promise.all([
        documentService.listDocuments(),
        learningService.getQuizHistory(20),
      ])
      setDocuments(docsRes.documents || [])
      setHistory(histRes.history || [])
    } catch {
      // ignore
    }
  }

  const loadHistory = async () => {
    try {
      const histRes = await learningService.getQuizHistory(20)
      setHistory(histRes.history || [])
    } catch {
      // ignore
    }
  }

  const handleStartGenerate = async () => {
    setGenerating(true)
    setIsGenerateModalOpen(false)
    try {
      const res = await learningService.generateQuiz(selectedDoc || null, questionCount, quizTopic.trim() || null)
      setAttempt({
        attempt_id: res.attempt_id,
        source: res.source,
        questions: res.questions,
      })
      setUserAnswers(new Array(res.questions.length).fill(-1))
      setCurrentStep(0)
      setResult(null)
      const focus = quizTopic.trim() ? ` (fokus: ${quizTopic.trim()})` : ''
      addToast(`Kuis baru berhasil dibuat${focus} (${res.questions.length} soal)!`, 'success')
    } catch (err: any) {
      addToast(err.message || 'Gagal membuat kuis.', 'error')
    } finally {
      setGenerating(false)
    }
  }

  const handleSelectOption = (optionIndex: number) => {
    const next = [...userAnswers]
    next[currentStep] = optionIndex
    setUserAnswers(next)
  }

  const handleSubmitQuiz = async () => {
    if (!attempt) return
    const unanswered = userAnswers.some((a) => a === -1)
    if (unanswered) {
      const confirm = window.confirm('Ada soal yang belum dijawab. Yakin ingin mengumpulkan?')
      if (!confirm) return
    }

    setGrading(true)
    try {
      const res = await learningService.gradeQuiz(attempt.attempt_id, userAnswers)
      setResult(res)
      loadInitialData() // refresh history
      addToast(`Kuis selesai! Skor: ${res.score} / ${res.total}`, 'success')
      if (res.saved_cards?.length) {
        addToast(`${res.saved_cards.length} soal yang salah ditambahkan ke kartu review SM-2!`, 'warning')
      }
    } catch (err: any) {
      addToast(err.message || 'Gagal mengoreksi kuis.', 'error')
    } finally {
      setGrading(false)
    }
  }

  const handleRetry = (source?: string | null) => {
    setSelectedDoc(source || '')
    setIsGenerateModalOpen(true)
  }

  const handleReview = async (attemptId: string) => {
    setReviewLoadingId(attemptId)
    try {
      const res = await learningService.getQuizAttempt(attemptId)
      setReviewing(res)
    } catch (err: any) {
      addToast(err.message || 'Gagal memuat pembahasan kuis.', 'error')
    } finally {
      setReviewLoadingId(null)
    }
  }

  const avgScore = history.length
    ? Math.round((history.reduce((acc, h) => acc + (h.score / (h.total || 1)) * 100, 0) / history.length))
    : 0

  return (
    <div className="page-container">
      <PageHeader
        title="AI Quiz Arena"
        subtitle="Uji dan validasi penguasaan materi dengan kuis pilihan ganda terstandar server."
        actions={
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <Button variant="secondary" icon="refresh" onClick={loadInitialData}>
              Muat Ulang
            </Button>
            <Button
              variant="primary"
              icon="plus"
              onClick={() => setIsGenerateModalOpen(true)}
              loading={generating}
            >
              Buat Kuis Baru
            </Button>
          </div>
        }
      />

      {/* Mode Tabs */}
      <div style={{ marginBottom: '1.25rem' }}>
        <Tabs
          items={[
            { id: 'play', label: 'Main Kuis', icon: 'quiz', badge: attempt ? attempt.questions.length : undefined },
            { id: 'history', label: 'Riwayat & Pembahasan', icon: 'progress', badge: history.length },
          ]}
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as 'play' | 'history')}
        />
      </div>

      {/* Metrics Row */}
      <div className="metrics-grid" style={{ marginBottom: '1.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <StatCard title="Rata-rata Skor" value={`${avgScore}%`} icon="award" subtitle="Dari seluruh riwayat kuis" />
        <StatCard title="Kuis Diselesaikan" value={history.length} icon="quiz" subtitle="Percobaan tersimpan" />
        <StatCard title="Dokumen Siap Uji" value={documents.length} icon="library" subtitle="Sumber materi kuis" />
      </div>

      {activeTab === 'history' ? (
        /* ====================== History & Review Tab ====================== */
        reviewing ? (
          /* Past Attempt Review */
          <div style={{ maxWidth: '720px', margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <Button variant="secondary" icon="arrow-left" size="sm" onClick={() => setReviewing(null)}>
                Kembali ke Riwayat
              </Button>
              {reviewing.score !== null && reviewing.score !== undefined && (
                <Badge variant={accuracyBadge(reviewing.total ? Math.round((reviewing.score / reviewing.total) * 100) : 0)}>
                  Skor: {reviewing.score} / {reviewing.total}
                </Badge>
              )}
            </div>

            <Card padding="md" style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div>
                <div style={{ fontWeight: '700', color: 'var(--text-primary)' }}>{reviewing.source || 'Semua Dokumen'}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>{formatDate(reviewing.created_at)} • {reviewing.questions.length} soal</div>
              </div>
              <Button variant="primary" size="sm" icon="refresh" onClick={() => handleRetry(reviewing.source)}>
                Ulangi Kuis Ini
              </Button>
            </Card>

            <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: '600', marginBottom: '1rem' }}>Kunci Jawaban:</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {reviewing.questions.map((q, idx) => (
                <Card key={idx} padding="md" style={{ borderLeft: '4px solid var(--color-success)' }}>
                  <div style={{ fontWeight: '600', fontSize: 'var(--text-sm)', marginBottom: '0.75rem' }}>
                    Soal {idx + 1}: {q.question}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {q.options.map((opt, optIdx) => {
                      const isCorrect = optIdx === q.correct_index
                      return (
                        <div
                          key={optIdx}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.6rem',
                            padding: '0.55rem 0.9rem',
                            borderRadius: 'var(--radius-md)',
                            background: isCorrect ? 'var(--color-success-bg)' : 'var(--color-paper-soft)',
                            border: `1px solid ${isCorrect ? 'var(--color-success)' : 'var(--color-rule)'}`,
                            color: isCorrect ? 'var(--color-success)' : 'var(--color-ink)',
                            opacity: isCorrect ? 1 : 0.75,
                          }}
                        >
                          <span
                            style={{
                              width: '22px',
                              height: '22px',
                              borderRadius: '50%',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 'var(--text-xs)',
                              fontWeight: '700',
                              flexShrink: 0,
                              background: isCorrect ? 'var(--color-success)' : 'var(--color-paper-raised)',
                              color: isCorrect ? '#fff' : 'var(--color-muted)',
                            }}
                          >
                            {String.fromCharCode(65 + optIdx)}
                          </span>
                          <span style={{ flex: 1, fontSize: 'var(--text-sm)' }}>{opt}</span>
                          {isCorrect && (
                            <Badge variant="success" size="sm" icon="check">
                              Jawaban Benar
                            </Badge>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </Card>
              ))}
            </div>
          </div>
        ) : history.length === 0 ? (
          <Card>
            <EmptyState
              icon="quiz"
              title="Belum Ada Riwayat Kuis"
              description="Selesaikan kuis pertama Anda, dan riwayat skor beserta pembahasannya akan muncul di sini."
              actionLabel="Buat Kuis Sekarang"
              actionIcon="sparkles"
              onAction={() => setIsGenerateModalOpen(true)}
            />
          </Card>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {history.map((h) => {
              const pct = h.total ? Math.round((h.score / h.total) * 100) : 0
              return (
                <Card key={h.id} padding="md" hover>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flex: 1, minWidth: '200px' }}>
                      <div
                        style={{
                          width: '48px',
                          height: '48px',
                          borderRadius: 'var(--radius-md)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          background:
                            pct >= 80 ? 'var(--color-success-bg)' : pct >= 50 ? 'var(--color-warning-bg)' : 'var(--color-error-bg)',
                          color: pct >= 80 ? 'var(--color-success)' : pct >= 50 ? 'var(--color-warning)' : 'var(--color-error)',
                          fontWeight: '800',
                          fontSize: '0.9rem',
                        }}
                      >
                        {pct}%
                      </div>
                      <div>
                        <div style={{ fontWeight: '600', fontSize: '0.9rem', color: 'var(--color-ink)' }}>
                          {h.source || 'Semua Dokumen'}
                        </div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)' }}>
                          {formatDate(h.created_at)} • {h.score} / {h.total} benar
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                      {h.attempt_id && (
                        <Button
                          variant="secondary"
                          size="sm"
                          icon="brain"
                          onClick={() => handleReview(h.attempt_id!)}
                          loading={h.attempt_id === reviewLoadingId}
                        >
                          Pembahasan
                        </Button>
                      )}
                      <Button variant="primary" size="sm" icon="refresh" onClick={() => handleRetry(h.source)}>
                        Ulangi
                      </Button>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        )
      ) : generating ? (
        <Card style={{ padding: '4rem', display: 'flex', justifyContent: 'center' }}>
          <Spinner size="lg" text="AI sedang menyusun paket soal kuis dari dokumen Anda..." />
        </Card>
      ) : result ? (
        /* Quiz Result Screen */
        <div style={{ maxWidth: '720px', margin: '0 auto' }}>
          <Card style={{ padding: '2.5rem', textAlign: 'center', marginBottom: '1.5rem' }} glow>
            <div style={{ width: '80px', height: '80px', borderRadius: '50%', background: 'oklch(from var(--color-accent) l c h / 0.15)', color: 'var(--color-accent)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem' }}>
              <Icon name="award" size={40} />
            </div>
            <h2 style={{ fontSize: '1.75rem', fontWeight: '700', color: 'var(--color-ink)', marginBottom: '0.5rem' }}>
              Hasil Evaluasi Kuis
            </h2>
            <div style={{ fontSize: '2.5rem', fontWeight: '800', color: 'var(--color-accent)', margin: '0.5rem 0' }}>
              {result.score} / {result.total}
            </div>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--color-muted)', marginBottom: '1.5rem' }}>
              Akurasi: {Math.round((result.score / (result.total || 1)) * 100)}%
            </p>
            {result.feedback && (
              <div style={{ padding: '1rem', background: 'var(--color-paper-soft)', borderRadius: 'var(--radius-md)', marginBottom: '1.5rem', textAlign: 'left', fontSize: 'var(--text-sm)' }}>
                {result.feedback}
              </div>
            )}
            <Button variant="primary" icon="refresh" onClick={() => setIsGenerateModalOpen(true)}>
              Coba Kuis Lain
            </Button>
          </Card>

          {/* Question Breakdown */}
          <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: '600', marginBottom: '1rem' }}>Rincian Jawaban:</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {result.details.map((d, idx) => {
              const q = attempt?.questions[idx]
              return (
                <Card key={idx} padding="md" style={{ borderLeft: `4px solid ${d.correct ? 'var(--color-success)' : 'var(--color-error)'}` }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', gap: '0.75rem' }}>
                    <span style={{ fontWeight: '600', fontSize: 'var(--text-sm)' }}>
                      Soal {idx + 1}: {d.question}
                    </span>
                    <Badge variant={d.correct ? 'success' : 'error'}>
                      {d.correct ? 'Benar' : 'Salah'}
                    </Badge>
                  </div>

                  {/* Opsi jawaban: hijau = benar, merah = pilihan user yang salah */}
                  {q?.options && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '0.75rem' }}>
                      {q.options.map((opt, optIdx) => {
                        const isCorrect = optIdx === d.correct_index
                        const isWrongPick = !d.correct && optIdx === userAnswers[idx]
                        const isMuted = !isCorrect && !isWrongPick
                        return (
                          <div
                            key={optIdx}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.6rem',
                              padding: '0.55rem 0.9rem',
                              borderRadius: 'var(--radius-md)',
                              background: isCorrect ? 'var(--color-success-bg)' : isWrongPick ? 'var(--color-error-bg)' : 'var(--color-paper-soft)',
                              border: `1px solid ${isCorrect ? 'var(--color-success)' : isWrongPick ? 'var(--color-error)' : 'var(--color-rule)'}`,
                              color: isCorrect ? 'var(--color-success)' : isWrongPick ? 'var(--color-error)' : 'var(--color-ink)',
                              opacity: isMuted ? 0.75 : 1,
                            }}
                          >
                            <span
                              style={{
                                width: '22px',
                                height: '22px',
                                borderRadius: '50%',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: 'var(--text-xs)',
                                fontWeight: '700',
                                flexShrink: 0,
                                background: isCorrect ? 'var(--color-success)' : isWrongPick ? 'var(--color-error)' : 'var(--color-paper-raised)',
                                color: isCorrect || isWrongPick ? '#fff' : 'var(--color-muted)',
                              }}
                            >
                              {String.fromCharCode(65 + optIdx)}
                            </span>
                            <span style={{ flex: 1, fontSize: 'var(--text-sm)' }}>{opt}</span>
                            {isCorrect && (
                              <Badge variant="success" size="sm" icon="check">
                                Jawaban Benar
                              </Badge>
                            )}
                            {isWrongPick && (
                              <Badge variant="error" size="sm" icon="x">
                                Pilihan Anda
                              </Badge>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )}

                  {d.explanation && (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '0.45rem',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-muted)',
                        background: 'var(--color-paper-soft)',
                        padding: '0.6rem 0.8rem',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--color-rule)',
                        lineHeight: '1.5',
                      }}
                    >
                      <Icon name="info" size={14} />
                      <span>{d.explanation}</span>
                    </div>
                  )}
                </Card>
              )
            })}
          </div>
        </div>
      ) : attempt ? (
        /* Active Quiz Stepper */
        <div style={{ maxWidth: '680px', margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <Badge variant="primary" dot>
              Soal {currentStep + 1} dari {attempt.questions.length}
            </Badge>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-muted)' }}>
              {attempt.source ? `Materi: ${attempt.source}` : 'Materi: Umum'}
            </span>
          </div>

          <Card style={{ padding: '2rem', marginBottom: '1.5rem' }}>
            <h3 style={{ fontSize: '1.15rem', fontWeight: '600', color: 'var(--color-ink)', lineHeight: '1.6', marginBottom: '1.5rem' }}>
              {attempt.questions[currentStep]?.question}
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {attempt.questions[currentStep]?.options.map((opt, optIdx) => {
                const isSelected = userAnswers[currentStep] === optIdx
                return (
                  <button
                    key={optIdx}
                    type="button"
                    onClick={() => handleSelectOption(optIdx)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.75rem',
                      padding: '0.85rem 1.2rem',
                      borderRadius: 'var(--radius-md)',
                      background: isSelected ? 'oklch(from var(--color-accent) l c h / 0.15)' : 'var(--color-paper-soft)',
                      border: `1px solid ${isSelected ? 'var(--color-accent)' : 'var(--color-rule)'}`,
                      color: isSelected ? 'var(--color-accent)' : 'var(--color-ink)',
                      textAlign: 'left',
                      fontWeight: isSelected ? '600' : '400',
                      transition: 'all var(--dur-fast)',
                      cursor: 'pointer',
                    }}
                  >
                    <span
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: isSelected ? 'var(--color-accent)' : 'var(--color-paper-raised)',
                        color: isSelected ? '#fff' : 'var(--color-muted)',
                        fontSize: 'var(--text-xs)',
                        fontWeight: '700',
                      }}
                    >
                      {String.fromCharCode(65 + optIdx)}
                    </span>
                    <span style={{ flex: 1, fontSize: 'var(--text-sm)' }}>{opt}</span>
                  </button>
                )
              })}
            </div>
          </Card>

          {/* Stepper Navigation */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Button
              variant="secondary"
              icon="arrow-left"
              onClick={() => setCurrentStep((prev) => Math.max(0, prev - 1))}
              disabled={currentStep === 0}
            >
              Sebelumnya
            </Button>

            {currentStep < attempt.questions.length - 1 ? (
              <Button
                variant="primary"
                icon="arrow-right"
                iconPosition="right"
                onClick={() => setCurrentStep((prev) => Math.min(attempt.questions.length - 1, prev + 1))}
              >
                Selanjutnya
              </Button>
            ) : (
              <Button
                variant="success"
                icon="check"
                onClick={handleSubmitQuiz}
                loading={grading}
              >
                Kumpulkan Jawaban
              </Button>
            )}
          </div>
        </div>
      ) : (
        /* Empty / Welcome State */
        <Card>
          <EmptyState
            icon="quiz"
            title="Mulai Uji Pemahaman Anda"
            description="Pilih dokumen yang sudah diunggah, dan biarkan AI menyusun soal evaluasi deterministik untuk mengukur daya serap materi."
            actionLabel="Generate Kuis Sekarang"
            actionIcon="sparkles"
            onAction={() => setIsGenerateModalOpen(true)}
          />
        </Card>
      )}

      {/* Generate Quiz Modal */}
      <Modal
        isOpen={isGenerateModalOpen}
        onClose={() => setIsGenerateModalOpen(false)}
        title="Buat Kuis Baru"
        subtitle="Pilih sumber materi dan jumlah soal kuis yang diinginkan."
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsGenerateModalOpen(false)}>
              Batal
            </Button>
            <Button variant="primary" icon="sparkles" onClick={handleStartGenerate}>
              Mulai Susun Kuis
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <Select
            label="Sumber Dokumen"
            value={selectedDoc}
            onChange={(e) => setSelectedDoc(e.target.value)}
            options={[
              { value: '', label: 'Semua Dokumen Terindeks' },
              ...documents.map((d) => ({ value: d.source, label: d.source })),
            ]}
          />

          <Input
            label="Topik / Fokus Materi (opsional)"
            placeholder="Contoh: VLAN, OSPF, subnetting..."
            value={quizTopic}
            onChange={(e) => setQuizTopic(e.target.value)}
          />
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '-0.75rem' }}>
            Kuis akan dicari dari chunk yang relevan dengan topik ini (misal dari weak-spots Anda).
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                Jumlah Soal
              </label>
              <Badge variant="primary">
                {questionCount} Soal Dipilih
              </Badge>
            </div>

            {/* Quick Presets */}
            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
              {[3, 5, 10, 15, 20].map((num) => (
                <button
                  key={num}
                  type="button"
                  onClick={() => setQuestionCount(num)}
                  style={{
                    flex: 1,
                    minWidth: '60px',
                    padding: '0.45rem 0.65rem',
                    borderRadius: 'var(--radius-sm)',
                    background: questionCount === num ? 'var(--accent)' : 'var(--bg-surface-raised)',
                    color: questionCount === num ? '#fff' : 'var(--text-primary)',
                    border: `1px solid ${questionCount === num ? 'var(--accent)' : 'var(--border-subtle)'}`,
                    fontWeight: '600',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                    transition: 'all var(--dur-fast)',
                  }}
                >
                  {num} Soal
                </button>
              ))}
            </div>

            {/* Custom Input & Range Slider */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--bg-surface-raised)', padding: '0.75rem 1rem', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)' }}>
              <input
                type="range"
                min={1}
                max={20}
                value={questionCount}
                onChange={(e) => setQuestionCount(Math.max(1, Math.min(20, Number(e.target.value))))}
                style={{ flex: 1, accentColor: 'var(--accent)', cursor: 'pointer' }}
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setQuestionCount((prev) => Math.max(1, prev - 1))}
                  style={{ width: '28px', height: '28px', padding: 0 }}
                >
                  -
                </Button>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={questionCount}
                  onChange={(e) => setQuestionCount(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                  style={{
                    width: '48px',
                    textAlign: 'center',
                    background: 'var(--bg-surface)',
                    border: '1px solid var(--border-default)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-primary)',
                    fontWeight: '700',
                    padding: '0.25rem',
                    fontSize: '0.9rem',
                  }}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setQuestionCount((prev) => Math.min(20, prev + 1))}
                  style={{ width: '28px', height: '28px', padding: 0 }}
                >
                  +
                </Button>
              </div>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
              Anda bebas menentukan jumlah soal mulai dari 1 hingga 20 soal sesuai kebutuhan.
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}
