/**
 * Centralized TypeScript Domain Types for Personal AI Knowledge Base
 */

export interface SourceRef {
  source: string
  page: number
  heading: string
  text: string
  distance: number
  chunk_index: number
}

export interface Message {
  id?: number
  session_id?: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceRef[] | null
  created_at?: string
}

export interface Session {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export interface DocumentInfo {
  source: string
  category: string
  chunks: number
  status: 'queued' | 'processing' | 'ready' | 'error'
  updated_at: string
}

export interface IngestJob {
  id: string
  source: string
  kind: string
  status: 'queued' | 'processing' | 'ready' | 'error'
  chunks: number
  error?: string
  created_at: string
}

export interface ReviewCard {
  card_id: string
  question: string
  answer?: string
  source?: string | null
  next_due: string
  interval_days: number
  lapses: number
  ease_factor?: number
  repetitions?: number
}

export interface AIFlashcard {
  front: string
  back: string
  source?: string
  page?: number | null
}

export interface RecommendationItem {
  type: string
  title: string
  description: string
  action: string
  topic?: string
  priority: 'high' | 'medium' | 'low'
}

export interface CardStats {
  total: number
  due_today: number
  avg_lapses: number
}

export interface Flashcard {
  heading: string
  content: string
}

export interface FlashcardStat {
  heading: string
  source?: string | null
  known_count: number
  unknown_count: number
  updated_at: string
}

export interface QuizQuestion {
  question: string
  options: string[]
  answer_index?: number
}

export interface QuizAttempt {
  attempt_id: string
  source?: string | null
  questions: QuizQuestion[]
}

export interface QuizQuestionDetail {
  question: string
  correct: boolean
  correct_index: number
  explanation?: string
}

export interface QuizGradeResult {
  score: number
  total: number
  correct: number[]
  details: QuizQuestionDetail[]
  feedback?: string
}

export interface QuizScoreItem {
  id: number
  source?: string | null
  score: number
  total: number
  attempt_id?: string | null
  created_at: string
}

export interface QuizAttemptDetail {
  attempt_id: string
  source?: string | null
  created_at: string
  score?: number | null
  total?: number | null
  questions: { question: string; options: string[]; correct_index: number }[]
}

export interface WeakSpot {
  topic: string
  score: number
  asked: number
  lapses: number
  wrong: number
}

export interface MasteryStat {
  source: string
  exposure: number
  correct: number
  wrong: number
  mastery: number
}

export interface DocumentProgress {
  source: string
  headings_covered: { heading: string; asked: number }[]
  total_questions: number
}

export interface AnnotationItem {
  id: string
  source: string
  chunk_id: string
  page?: number | null
  text: string
  tags: string[]
  created_at: string
  updated_at: string
}

export interface GlossaryTerm {
  id?: number
  term: string
  definition: string
  source: string
  page?: number | null
  category: string
  verified: boolean
  created_at?: string
  updated_at?: string
  exists?: boolean
}

export interface MindmapNode {
  name: string
  children: MindmapNode[]
}

export interface SystemMetrics {
  requests?: number
  latency_ms_p50?: number
  latency_ms_p95?: number
  latency_ms_window?: number
  uptime_sec?: number
  disk?: {
    persist_free_mb: number
    persist_total_mb: number
  }
}

export interface PrivacyInfo {
  provider_label: string
  external_data_flow: boolean
  redaction_enabled: boolean
  retention: {
    chat_days: number
    cache_max_days: number
  }
  disclosure_text: string
}

export interface RepeatedQuestionItem {
  question: string
  count: number
  last_asked: string
}
