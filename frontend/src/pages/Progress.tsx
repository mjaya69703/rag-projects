import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Icon,
  PageHeader,
  Spinner,
  StatCard,
} from '../shared/components'
import { useToast } from '../shared/hooks'
import { glossaryService, learningService, systemService } from '../shared/services'
import type { CardStats, DocumentProgress, MasteryStat, MindmapNode, RecommendationItem, RepeatedQuestionItem, SystemMetrics, WeakSpot } from '../shared/types'

function formatStorage(mb: number | undefined): string {
  if (!mb) return '0 MB'
  if (mb >= 1024) return (mb / 1024).toFixed(1) + ' GB'
  return mb.toFixed(0) + ' MB'
}

function MindmapTree({ node, depth = 0 }: { node: MindmapNode; depth?: number }) {
  const hasChildren = node.children && node.children.length > 0
  return (
    <div style={{ marginLeft: depth === 0 ? 0 : '0.85rem', borderLeft: depth > 0 ? '1px solid var(--border-subtle)' : 'none', paddingLeft: depth > 0 ? '0.85rem' : 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.3rem 0' }}>
        <Icon name="tag" size={14} style={{ color: depth === 0 ? 'var(--accent)' : 'var(--text-muted)', flexShrink: 0 }} />
        <span
          style={{
            fontSize: depth === 0 ? '0.92rem' : '0.82rem',
            fontWeight: depth === 0 ? '700' : '500',
            color: depth === 0 ? 'var(--text-primary)' : 'var(--text-secondary)',
            lineHeight: '1.4',
          }}
        >
          {node.name}
        </span>
      </div>
      {hasChildren && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {node.children.map((child, i) => (
            <MindmapTree key={i} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function Progress() {
  const navigate = useNavigate()
  const { addToast } = useToast()
  const [weakSpots, setWeakSpots] = useState<WeakSpot[]>([])
  const [mastery, setMastery] = useState<MasteryStat[]>([])
  const [progress, setProgress] = useState<DocumentProgress[]>([])
  const [metrics, setMetrics] = useState<SystemMetrics>({})
  const [cardStats, setCardStats] = useState<CardStats>({ total: 0, due_today: 0, avg_lapses: 0 })
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([])
  const [repeatedQuestions, setRepeatedQuestions] = useState<RepeatedQuestionItem[]>([])
  const [mindmap, setMindmap] = useState<MindmapNode | null>(null)
  const [mindmapLoading, setMindmapLoading] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [weakRes, masteryRes, progRes, metricsRes, repRes, recRes] = await Promise.all([
        learningService.getWeakSpots(8),
        learningService.getMastery(),
        learningService.getProgress(),
        systemService.getMetrics(),
        systemService.getRepeatedQuestions(7, 2),
        learningService.getRecommendations().catch(() => ({ recommendations: [], card_stats: { total: 0, due_today: 0, avg_lapses: 0 } })),
      ])
      setWeakSpots(weakRes.weak_spots || [])
      setMastery(masteryRes.mastery || [])
      setProgress(progRes.progress || [])
      setMetrics(metricsRes || {})
      setRepeatedQuestions(repRes.questions || [])
      setRecommendations((recRes as any).recommendations || [])
      setCardStats((recRes as any).card_stats || { total: 0, due_today: 0, avg_lapses: 0 })
      loadMindmap()
    } catch (err: any) {
      addToast(err.message || 'Gagal memuat analitik.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const loadMindmap = async (silent = true) => {
    setMindmapLoading(true)
    try {
      const res = await glossaryService.getMindmap(null)
      setMindmap(res.mindmap || null)
    } catch {
      setMindmap(null)
    } finally {
      setMindmapLoading(false)
    }
  }

  const handleExportReport = () => {
    const reportData = {
      timestamp: new Date().toISOString(),
      summary: {
        total_rag_queries: metrics.queries || 0,
        cache_hits: metrics.cache_hits || 0,
        cache_misses: metrics.cache_misses || 0,
        due_flashcards: cardStats.due_today,
        total_flashcards: cardStats.total,
      },
      weak_spots: weakSpots,
      mastery: mastery,
      progress: progress,
    }
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `learning_report_${new Date().toISOString().substring(0, 10)}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    addToast('Laporan perkembangan belajar berhasil diunduh!', 'success')
  }

  return (
    <div className="page-container" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <PageHeader
        title="Learning Analytics & Diagnostics"
        subtitle="Pusat komando belajar: pantau daya serap materi, rekomendasi AI personal, dan perbaiki titik lemah secara instan."
        actions={
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <Button variant="secondary" icon="download" onClick={handleExportReport}>
              Unduh Rapor Belajar
            </Button>
            <Button variant="secondary" icon="refresh" onClick={loadData}>
              Muat Ulang
            </Button>
          </div>
        }
      />

      {/* Action Center Bar - Quick Jump */}
      <Card padding="md" style={{ background: 'var(--glass-bg)', backdropFilter: 'blur(12px)', border: '1px solid var(--glass-border)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.78rem', fontWeight: '700', textTransform: 'uppercase', color: 'var(--accent)', letterSpacing: '0.05em' }}>
              ⚡ Aksi Cepat Belajar
            </span>
            <h4 style={{ fontSize: '1rem', fontWeight: '700', color: 'var(--text-primary)', marginTop: '0.2rem' }}>
              Mau fokus belajar apa hari ini?
            </h4>
          </div>

          <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
            <Button
              variant="primary"
              icon="clock"
              onClick={() => navigate('/flashcards')}
            >
              Uji Harian SM-2 ({cardStats.due_today} Due)
            </Button>

            <Button
              variant="secondary"
              icon="quiz"
              onClick={() => navigate('/quiz')}
            >
              Buat Kuis AI
            </Button>

            <Button
              variant="secondary"
              icon="chat"
              onClick={() => navigate('/')}
            >
              Tanya di Chat
            </Button>
          </div>
        </div>
      </Card>

      {loading ? (
        <Card style={{ padding: '4rem', display: 'flex', justifyContent: 'center' }}>
          <Spinner size="lg" text="Menganalisis perkembangan belajar..." />
        </Card>
      ) : (
        <>
          {/* Top KPI Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))', gap: '1rem' }}>
            <StatCard
              title="Total Pertanyaan RAG"
              value={metrics.queries || 0}
              icon="zap"
              subtitle={`Cache: ${metrics.cache_hits || 0} hit • ${metrics.cache_misses || 0} miss`}
            />
            <StatCard
              title="Kartu Due Review"
              value={cardStats.due_today}
              icon="clock"
              subtitle={`Dari total ${cardStats.total} kartu aktif`}
            />
            <StatCard
              title="Latency P50"
              value={`${metrics.latency_ms_p50 || 0} ms`}
              icon="clock"
              subtitle={`P95: ${metrics.latency_ms_p95 || 0} ms`}
            />
            <StatCard
              title="Kapasitas Disk Free"
              value={formatStorage(metrics.disk?.persist_free_mb)}
              icon="library"
              subtitle={`Dari total ${formatStorage(metrics.disk?.persist_total_mb)}`}
            />
          </div>

          {/* AI Study Recommendations */}
          {recommendations.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.85rem' }}>
                <Icon name="sparkles" size={18} />
                <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  💡 Rekomendasi Belajar Personal dari AI
                </h3>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))', gap: '1rem' }}>
                {recommendations.map((rec, idx) => (
                  <Card key={idx} padding="md" style={{ borderLeft: `4px solid ${rec.priority === 'high' ? 'var(--error)' : 'var(--accent)'}` }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                      <span style={{ fontWeight: '700', fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                        {rec.title}
                      </span>
                      <Badge variant={rec.priority === 'high' ? 'error' : 'secondary'} size="sm">
                        {rec.priority === 'high' ? 'Penting' : 'Saran'}
                      </Badge>
                    </div>

                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.5', marginBottom: '0.85rem' }}>
                      {rec.description}
                    </p>

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                      {rec.type === 'flashcards' ? (
                        <Button variant="primary" size="sm" icon="cards" onClick={() => navigate('/flashcards')}>
                          Latih Kartu Sekarang
                        </Button>
                      ) : rec.type === 'weak_spot' ? (
                        <Button variant="secondary" size="sm" icon="quiz" onClick={() => navigate(`/quiz?topic=${encodeURIComponent(rec.topic || '')}`)}>
                          Latih Kuis Topik Ini
                        </Button>
                      ) : (
                        <Button variant="secondary" size="sm" icon="quiz" onClick={() => navigate('/quiz')}>
                          Mulai Kuis Baru
                        </Button>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Diagnostics Section */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
            {/* Weak Spots Diagnostic */}
            <Card padding="lg">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  Area Perlu Pengulangan (Weak-spots)
                </h3>
                <Badge variant="error">Perlu Review</Badge>
              </div>

              {weakSpots.length === 0 ? (
                <EmptyState
                  icon="award"
                  title="Tidak Ada Titik Lemah Signifikan"
                  description="Bagus! Anda menjawab sebagian besar kuis dan flashcard dengan benar."
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {weakSpots.map((ws, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '1rem 1.25rem',
                        background: 'var(--bg-surface-raised)',
                        borderRadius: 'var(--radius-md)',
                        borderLeft: '4px solid var(--error)',
                        boxShadow: 'var(--shadow-sm)',
                        flexWrap: 'wrap',
                        gap: '0.75rem',
                      }}
                    >
                      <div style={{ flex: 1, minWidth: '200px' }}>
                        <div style={{ fontWeight: '700', fontSize: '0.92rem', color: 'var(--text-primary)' }}>{ws.topic}</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.3rem' }}>
                          Ditanya: {ws.asked}x • Lupa: {ws.lapses}x • Salah: {ws.wrong}x
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <Badge variant="warning">Skor {ws.score}</Badge>
                        <Button
                          variant="secondary"
                          size="sm"
                          icon="quiz"
                          onClick={() => navigate(`/quiz?topic=${encodeURIComponent(ws.topic)}`)}
                          title="Latih remedial topik ini"
                        >
                          Latih Kuis
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            {/* Document Mastery Progress */}
            <Card padding="lg">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  Tingkat Penguasaan Dokumen (Mastery)
                </h3>
                <Badge variant="success">SM-2 Correctness</Badge>
              </div>

              {mastery.length === 0 ? (
                <EmptyState
                  icon="library"
                  title="Belum Ada Data Penguasaan"
                  description="Kerjakan kuis atau flashcard untuk mengukur tingkat pemahaman tiap dokumen."
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                  {mastery.map((m, idx) => {
                    const pct = Math.round((m.mastery || 0) * 100)
                    return (
                      <div key={idx}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem', fontSize: '0.85rem' }}>
                          <span style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{m.source}</span>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                              {m.correct} benar / {m.exposure} diuji
                            </span>
                            <span style={{ fontWeight: '700', color: pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)' }}>
                              {pct}%
                            </span>
                          </div>
                        </div>

                        <div style={{ width: '100%', height: '8px', background: 'var(--border-subtle)', borderRadius: '4px', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${pct}%`,
                              height: '100%',
                              background: pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)',
                              transition: 'width 0.6s ease-in-out',
                            }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Card>
          </div>
        {/* Repeated Questions Thermometer */}
          {repeatedQuestions.length > 0 && (
            <Card padding="lg">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  Pertanyaan Berulang (7 Hari)
                </h3>
                <Badge variant="primary">Termometer Fokus</Badge>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {repeatedQuestions.slice(0, 10).map((rq, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '0.75rem',
                      padding: '0.85rem 1rem',
                      background: 'var(--bg-surface-raised)',
                      borderRadius: 'var(--radius-md)',
                      borderLeft: '3px solid var(--accent)',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: '600', fontSize: '0.88rem', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={rq.question}>
                        {rq.question}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                        Terakhir: {new Date(rq.last_asked).toLocaleDateString('id-ID')}
                      </div>
                    </div>
                    <Badge variant={rq.count >= 5 ? 'error' : rq.count >= 3 ? 'warning' : 'secondary'} size="sm">
                      {rq.count}x ditanya
                    </Badge>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Concept Mindmap */}
          <Card padding="lg">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <h3 style={{ fontSize: '1.15rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                Peta Konsep Dokumen (Mindmap)
              </h3>
              <Button variant="ghost" size="sm" icon="refresh" onClick={() => loadMindmap(false)} loading={mindmapLoading}>
                Muat Ulang
              </Button>
            </div>
            {mindmap ? (
              <MindmapTree node={mindmap} />
            ) : (
              <EmptyState
                icon="mindmap"
                title="Belum Ada Peta Konsep"
                description="Mindmap dibangun dari heading dokumen yang terindeks di perpustakaan Anda."
              />
            )}
          </Card>
        </>
      )}
    </div>
  )
}
