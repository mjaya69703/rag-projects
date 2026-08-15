import React, { useEffect, useState } from 'react'
import {
  Badge,
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  Icon,
  Input,
  Markdown,
  Modal,
  PageHeader,
  Select,
  Spinner,
  StatCard,
  Tabs,
} from '../shared/components'
import { useToast } from '../shared/hooks'
import { documentService, learningService } from '../shared/services'
import type { AIFlashcard, CardStats, DocumentInfo, Flashcard, ReviewCard } from '../shared/types'

export default function Flashcards() {
  const { addToast } = useToast()
  const [mode, setMode] = useState<'due' | 'deck' | 'heading'>('due')
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [selectedDoc, setSelectedDoc] = useState<string>('')

  // SM-2 Review State
  const [dueCards, setDueCards] = useState<ReviewCard[]>([])
  const [deckCards, setDeckCards] = useState<ReviewCard[]>([])
  const [cardStats, setCardStats] = useState<CardStats>({ total: 0, due_today: 0, avg_lapses: 0 })
  const [currentIndex, setCurrentIndex] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  // Chunk Flashcards Fallback
  const [chunkCards, setChunkCards] = useState<Flashcard[]>([])

  // AI Flashcards Modal
  const [isGenerateModalOpen, setIsGenerateModalOpen] = useState(false)
  const [genDoc, setGenDoc] = useState('')
  const [genCount, setGenCount] = useState(5)
  const [generating, setGenerating] = useState(false)
  const [generatedPreview, setGeneratedPreview] = useState<AIFlashcard[]>([])

  // Custom Card Modal
  const [isCustomModalOpen, setIsCustomModalOpen] = useState(false)
  const [customQuestion, setCustomQuestion] = useState('')
  const [customAnswer, setCustomAnswer] = useState('')
  const [customSource, setCustomSource] = useState('')
  const [savingCustom, setSavingCustom] = useState(false)

  // Delete Card Confirm
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null)
  const [deletingCard, setDeletingCard] = useState(false)

  useEffect(() => {
    loadDocuments()
    loadDueCards()
  }, [])

  useEffect(() => {
    if (mode === 'due') {
      loadDueCards(selectedDoc)
    } else if (mode === 'deck') {
      loadDeckCards(selectedDoc)
    } else if (mode === 'heading') {
      loadChunkCards(selectedDoc)
    }
  }, [mode, selectedDoc])

  const loadDocuments = async () => {
    try {
      const res = await documentService.listDocuments()
      setDocuments(res.documents || [])
    } catch {
      // ignore
    }
  }

  const loadDueCards = async (doc?: string) => {
    setLoading(true)
    try {
      const res = await learningService.getDueCards(doc || null, 30)
      setDueCards(res.cards || [])
      setCardStats(res.stats || { total: 0, due_today: 0, avg_lapses: 0 })
      setCurrentIndex(0)
      setIsFlipped(false)
    } catch (err: any) {
      addToast(err.message || 'Gagal memuat kartu review.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const loadDeckCards = async (doc?: string) => {
    setLoading(true)
    try {
      const res = await learningService.listCards(doc || null, 100)
      setDeckCards(res.cards || [])
      setCardStats(res.stats || { total: 0, due_today: 0, avg_lapses: 0 })
    } catch (err: any) {
      addToast(err.message || 'Gagal memuat daftar dek kartu.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const loadChunkCards = async (doc?: string) => {
    setLoading(true)
    try {
      const res = await learningService.getFlashcards(doc || null, 30)
      setChunkCards(res.cards || [])
      setCurrentIndex(0)
      setIsFlipped(false)
    } catch (err: any) {
      addToast(err.message || 'Gagal memuat flashcard chunk dokumen.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleRatingAnswer = async (rating: number) => {
    if (dueCards.length === 0) return
    const card = dueCards[currentIndex]
    if (!card) return

    setSubmitting(true)
    try {
      await learningService.answerCard(card.card_id, rating)
      const labels = ['', 'Ditandai lupa, akan diulang segera', 'Ditandai ragu, interval 1 hari', 'Bagus! Dijadwalkan ulang sesuai SM-2', 'Luar biasa! Penguasaan materi meningkat']
      addToast(labels[rating] || 'Hasil review dicatat!', rating >= 3 ? 'success' : 'warning')

      if (currentIndex < dueCards.length - 1) {
        setCurrentIndex((prev) => prev + 1)
        setIsFlipped(false)
      } else {
        loadDueCards(selectedDoc)
      }
    } catch (err: any) {
      addToast(err.message || 'Gagal mencatat respon review.', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const handleStartGenerate = async () => {
    setGenerating(true)
    try {
      const res = await learningService.generateFlashcards(genDoc || null, genCount, true)
      setGeneratedPreview(res.cards || [])
      addToast(`Berhasil menyusun ${res.cards?.length || 0} flashcard AI berkualitas tinggi!`, 'success')
      setIsGenerateModalOpen(false)
      loadDueCards(selectedDoc)
      loadDeckCards(selectedDoc)
    } catch (err: any) {
      addToast(err.message || 'Gagal menyusun flashcard AI.', 'error')
    } finally {
      setGenerating(false)
    }
  }

  const handleCreateCustom = async () => {
    if (!customQuestion.trim() || !customAnswer.trim()) {
      addToast('Pertanyaan dan jawaban wajib diisi.', 'warning')
      return
    }

    setSavingCustom(true)
    try {
      await learningService.createCustomCard(customQuestion, customAnswer, customSource || null)
      addToast('Kartu kustom berhasil ditambahkan ke dek!', 'success')
      setIsCustomModalOpen(false)
      setCustomQuestion('')
      setCustomAnswer('')
      setCustomSource('')
      loadDueCards(selectedDoc)
      loadDeckCards(selectedDoc)
    } catch (err: any) {
      addToast(err.message || 'Gagal membuat kartu.', 'error')
    } finally {
      setSavingCustom(false)
    }
  }

  const handleDeleteCard = async () => {
    if (!deleteTargetId) return
    setDeletingCard(true)
    try {
      await learningService.deleteCard(deleteTargetId)
      addToast('Kartu berhasil dihapus dari dek.', 'info')
      setDeleteTargetId(null)
      loadDueCards(selectedDoc)
      loadDeckCards(selectedDoc)
    } catch (err: any) {
      addToast(err.message || 'Gagal menghapus kartu.', 'error')
    } finally {
      setDeletingCard(false)
    }
  }

  const activeCards = mode === 'due' ? dueCards : chunkCards
  const currentCard = activeCards[currentIndex]

  return (
    <div className="page-container">
      <PageHeader
        title="3D Spaced Repetition Flashcards"
        subtitle="Hafalkan dan kuasai konsep kunci materi dengan algoritma penjadwalan cerdas SM-2."
        actions={
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <Button
              variant="secondary"
              icon="sparkles"
              onClick={() => {
                setGenDoc(selectedDoc || '')
                setIsGenerateModalOpen(true)
              }}
            >
              Generate AI Flashcards
            </Button>
            <Button
              variant="primary"
              icon="plus"
              onClick={() => {
                setCustomSource(selectedDoc || '')
                setIsCustomModalOpen(true)
              }}
            >
              Buat Kartu Manual
            </Button>
          </div>
        }
      />

      {/* Mode Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <Tabs
          items={[
            { id: 'due', label: 'Uji Harian (Due SM-2)', icon: 'clock', badge: cardStats.due_today },
            { id: 'deck', label: 'Kelola Dek Kartu', icon: 'cards', badge: cardStats.total },
            { id: 'heading', label: 'Eksplorasi Dokumen', icon: 'library' },
          ]}
          activeId={mode}
          onChange={(id) => setMode(id as any)}
        />

        <div style={{ minWidth: '220px' }}>
          <Select
            value={selectedDoc}
            onChange={(e) => setSelectedDoc(e.target.value)}
            options={[
              { value: '', label: 'Semua Dokumen' },
              ...documents.map((d) => ({ value: d.source, label: d.source })),
            ]}
          />
        </div>
      </div>

      {/* KPI Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.25rem', marginBottom: '1.5rem' }}>
        <StatCard title="Kartu Due Hari Ini" value={cardStats.due_today} icon="clock" subtitle="Perlu diulang sekarang" />
        <StatCard title="Total Kartu Aktif" value={cardStats.total} icon="cards" subtitle="Tersimpan dalam memori SM-2" />
        <StatCard title="Rata-rata Lapses" value={cardStats.avg_lapses} icon="brain" subtitle="Frekuensi lupa materi" />
      </div>

      {/* Main Content Area */}
      {loading ? (
        <Card style={{ padding: '4rem', display: 'flex', justifyContent: 'center' }}>
          <Spinner size="lg" text="Memuat dek kartu flashcard..." />
        </Card>
      ) : mode === 'deck' ? (
        /* Deck Library Manager View */
        deckCards.length === 0 ? (
          <Card>
            <EmptyState
              icon="cards"
              title="Dek Kartu Masih Kosong"
              description="Belum ada flashcard yang dibuat. Gunakan AI untuk membuat flashcard otomatis dari dokumen Anda atau buat kartu manual."
              actionLabel="Generate AI Flashcards"
              actionIcon="sparkles"
              onAction={() => {
                setGenDoc(selectedDoc || '')
                setIsGenerateModalOpen(true)
              }}
            />
          </Card>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '1.25rem' }}>
            {deckCards.map((card) => (
              <Card key={card.card_id} padding="md" hover>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem', gap: '0.5rem' }}>
                  <Badge variant="primary" size="sm">
                    {card.source || 'Umum'}
                  </Badge>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Int: {card.interval_days}h • Rep: {card.repetitions || 0}
                    </span>
                    <button
                      type="button"
                      onClick={() => setDeleteTargetId(card.card_id)}
                      style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '2px' }}
                      title="Hapus Kartu"
                    >
                      <Icon name="trash" size={14} />
                    </button>
                  </div>
                </div>

                <div style={{ fontWeight: '700', fontSize: '0.95rem', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                  {card.question}
                </div>

                {card.answer && (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', background: 'var(--bg-surface-raised)', padding: '0.65rem 0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginBottom: '0.75rem', maxHeight: '120px', overflowY: 'auto' }}>
                    <Markdown content={card.answer} />
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.5rem' }}>
                  <span>Jadwal: {card.next_due ? card.next_due.substring(0, 10) : 'Hari ini'}</span>
                  <span>Lapses: {card.lapses}x</span>
                </div>
              </Card>
            ))}
          </div>
        )
      ) : activeCards.length === 0 ? (
        /* Empty State for Review */
        <Card>
          <EmptyState
            icon="award"
            title="Semua Kartu Hari Ini Sudah Tuntas!"
            description={mode === 'due' ? "Hebat! Tidak ada kartu review yang jatuh tempo untuk saat ini. Anda bisa membuat flashcard baru atau melihat seluruh dek." : "Tidak ada flashcard ditemukan untuk filter ini."}
            actionLabel="Generate AI Flashcard Baru"
            actionIcon="sparkles"
            onAction={() => {
              setGenDoc(selectedDoc || '')
              setIsGenerateModalOpen(true)
            }}
          />
        </Card>
      ) : (
        /* 3D Interactive Flip Card Arena */
        <div style={{ maxWidth: '640px', margin: '0 auto' }}>
          {/* Card Counter & Navigation */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem' }}>
            <Badge variant="primary" dot>
              Kartu {currentIndex + 1} dari {activeCards.length}
            </Badge>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Klik kartu untuk membalik (Flip)
            </span>
          </div>

          {/* 3D Card Box */}
          <div
            onClick={() => setIsFlipped(!isFlipped)}
            style={{
              perspective: '1200px',
              minHeight: '340px',
              cursor: 'pointer',
              marginBottom: '1.5rem',
            }}
          >
            <div
              style={{
                position: 'relative',
                width: '100%',
                minHeight: '340px',
                transition: 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
                transformStyle: 'preserve-3d',
                transform: isFlipped ? 'rotateY(180deg)' : 'none',
              }}
            >
              {/* Front Side */}
              <div
                style={{
                  position: isFlipped ? 'absolute' : 'relative',
                  width: '100%',
                  minHeight: '340px',
                  backfaceVisibility: 'hidden',
                  borderRadius: 'var(--radius-xl)',
                  background: 'var(--glass-bg)',
                  border: '1px solid var(--glass-border)',
                  boxShadow: 'var(--glass-shadow)',
                  backdropFilter: 'blur(16px)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  padding: '2rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Badge variant="secondary" icon="quiz">
                    Pertanyaan / Konsep
                  </Badge>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    <Icon name="file" size={13} />
                    {currentCard && 'source' in currentCard ? currentCard.source : 'Dokumen'}
                  </span>
                </div>

                <div style={{ margin: '1.5rem 0', textAlign: 'center' }}>
                  <h3 style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-primary)', lineHeight: '1.6' }}>
                    {currentCard && ('question' in currentCard ? currentCard.question : currentCard.heading)}
                  </h3>
                </div>

                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.4rem', textAlign: 'center', fontSize: '0.8rem', color: 'var(--accent)', fontWeight: '600' }}>
                  <Icon name="refresh" size={14} />
                  Klik untuk melihat jawaban & penjelasan
                </div>
              </div>

              {/* Back Side */}
              <div
                style={{
                  position: isFlipped ? 'relative' : 'absolute',
                  width: '100%',
                  minHeight: '340px',
                  backfaceVisibility: 'hidden',
                  transform: 'rotateY(180deg)',
                  borderRadius: 'var(--radius-xl)',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-default)',
                  boxShadow: 'var(--shadow-lg)',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  padding: '2rem',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Badge variant="success" icon="check">
                    Kunci Jawaban & Penjelasan
                  </Badge>
                  <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    {currentCard && 'source' in currentCard ? currentCard.source : ''}
                  </span>
                </div>

                <div style={{ margin: '1rem 0', textAlign: 'left', maxHeight: '180px', overflowY: 'auto', paddingRight: '0.5rem' }}>
                  {currentCard && 'answer' in currentCard && currentCard.answer ? (
                    <Markdown content={currentCard.answer} />
                  ) : currentCard && 'content' in currentCard ? (
                    <Markdown content={currentCard.content} />
                  ) : (
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.92rem' }}>
                      {currentCard && 'question' in currentCard ? currentCard.question : ''}
                    </p>
                  )}
                </div>

                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>
                  Evaluasi tingkat pemahaman Anda di bawah untuk menjadwalkan repetisi berikutnya
                </div>
              </div>
            </div>
          </div>

          {/* SM-2 Rating Controls (Visible when flipped in Due mode) */}
          {mode === 'due' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem', animation: 'fadeIn 0.2s ease-out' }}>
              <Button
                variant="danger"
                size="md"
                icon="x"
                className="btn--stack"
                onClick={() => handleRatingAnswer(1)}
                loading={submitting}
              >
                <span>Lupa</span>
                <span className="btn__hint">Ulangi Segera</span>
              </Button>

              <Button
                variant="warning"
                size="md"
                icon="alert"
                className="btn--stack"
                onClick={() => handleRatingAnswer(2)}
                loading={submitting}
              >
                <span>Ragu</span>
                <span className="btn__hint">+1 Hari</span>
              </Button>

              <Button
                variant="success"
                size="md"
                icon="check"
                className="btn--stack"
                onClick={() => handleRatingAnswer(3)}
                loading={submitting}
              >
                <span>Ingat</span>
                <span className="btn__hint">+6 Hari</span>
              </Button>

              <Button
                variant="primary"
                size="md"
                icon="award"
                className="btn--stack"
                onClick={() => handleRatingAnswer(4)}
                loading={submitting}
              >
                <span>Sangat Paham</span>
                <span className="btn__hint">Perpanjang</span>
              </Button>
            </div>
          )}

          {/* Next / Prev Buttons for Heading Mode */}
          {mode === 'heading' && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Button
                variant="secondary"
                icon="arrow-left"
                disabled={currentIndex === 0}
                onClick={() => {
                  setCurrentIndex((prev) => Math.max(0, prev - 1))
                  setIsFlipped(false)
                }}
              >
                Sebelumnya
              </Button>
              <Button
                variant="primary"
                icon="arrow-right"
                iconPosition="right"
                disabled={currentIndex >= activeCards.length - 1}
                onClick={() => {
                  setCurrentIndex((prev) => Math.min(activeCards.length - 1, prev + 1))
                  setIsFlipped(false)
                }}
              >
                Selanjutnya
              </Button>
            </div>
          )}
        </div>
      )}

      {/* AI Flashcard Generator Modal */}
      <Modal
        isOpen={isGenerateModalOpen}
        onClose={() => setIsGenerateModalOpen(false)}
        title="✨ Generate AI Flashcards"
        subtitle="AI akan membaca isi dokumen dan membuat kartu tanya-jawab konsep esensial secara otomatis."
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsGenerateModalOpen(false)} disabled={generating}>
              Batal
            </Button>
            <Button variant="primary" icon="sparkles" onClick={handleStartGenerate} loading={generating}>
              Mulai Susun Flashcards
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          <Select
            label="Pilih Dokumen Sumber"
            value={genDoc}
            onChange={(e) => setGenDoc(e.target.value)}
            options={[
              { value: '', label: 'Semua Dokumen Terindeks' },
              ...documents.map((d) => ({ value: d.source, label: d.source })),
            ]}
          />

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
              <label style={{ fontSize: '0.78rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
                Jumlah Kartu Flashcard
              </label>
              <Badge variant="primary">{genCount} Kartu</Badge>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {[3, 5, 10, 15, 20].map((num) => (
                <button
                  key={num}
                  type="button"
                  onClick={() => setGenCount(num)}
                  style={{
                    flex: 1,
                    minWidth: '55px',
                    padding: '0.45rem',
                    borderRadius: 'var(--radius-sm)',
                    background: genCount === num ? 'var(--accent)' : 'var(--bg-surface-raised)',
                    color: genCount === num ? '#fff' : 'var(--text-primary)',
                    border: `1px solid ${genCount === num ? 'var(--accent)' : 'var(--border-subtle)'}`,
                    fontWeight: '600',
                    fontSize: '0.82rem',
                    cursor: 'pointer',
                  }}
                >
                  {num} Kartu
                </button>
              ))}
            </div>
          </div>
        </div>
      </Modal>

      {/* Custom Card Modal */}
      <Modal
        isOpen={isCustomModalOpen}
        onClose={() => setIsCustomModalOpen(false)}
        title="+ Buat Kartu Flashcard Manual"
        subtitle="Tambahkan pertanyaan dan jawaban kustom Anda ke dalam memori Spaced Repetition."
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsCustomModalOpen(false)} disabled={savingCustom}>
              Batal
            </Button>
            <Button variant="primary" icon="check" onClick={handleCreateCustom} loading={savingCustom}>
              Simpan ke Dek
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Pertanyaan / Konsep (Bagian Depan)"
            placeholder="Contoh: Apa kegunaan port 80 dan 443 pada web server?"
            value={customQuestion}
            onChange={(e) => setCustomQuestion(e.target.value)}
          />

          <div className="form-group">
            <label className="form-label">Jawaban / Penjelasan (Bagian Belakang)</label>
            <textarea
              className="form-input"
              rows={4}
              placeholder="Tuliskan jawaban yang ringkas dan padat..."
              value={customAnswer}
              onChange={(e) => setCustomAnswer(e.target.value)}
            />
          </div>

          <Select
            label="Kaitkan Dokumen Sumber (Opsional)"
            value={customSource}
            onChange={(e) => setCustomSource(e.target.value)}
            options={[
              { value: '', label: 'Umum (Tanpa Dokumen Tertentu)' },
              ...documents.map((d) => ({ value: d.source, label: d.source })),
            ]}
          />
        </div>
      </Modal>

      {/* Delete Card Confirm */}
      <ConfirmDialog
        isOpen={!!deleteTargetId}
        title="Hapus Kartu Flashcard"
        description="Apakah Anda yakin ingin menghapus kartu ini dari dek Spaced Repetition?"
        confirmText="Hapus Kartu"
        variant="danger"
        loading={deletingCard}
        onConfirm={handleDeleteCard}
        onCancel={() => setDeleteTargetId(null)}
      />
    </div>
  )
}
