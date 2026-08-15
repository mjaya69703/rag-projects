/** Klien API: wrapper fetch dengan parsing JSON + pesan error yang jelas. */
export class ApiError extends Error {
  status: number

  constructor(message: string, status = 0) {
    super(message)
    this.status = status
  }
}

// Event yang dipakai indikator status API (sidebar) untuk deteksi "degraded":
// request aplikasi gagal walau /health masih ok.
function dispatchApiError() {
  window.dispatchEvent(new CustomEvent('kb:api-error'))
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string>) || {}),
  }
  let response: Response
  try {
    response = await fetch(path, { ...options, headers })
  } catch (error) {
    dispatchApiError()
    throw error
  }
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    dispatchApiError()
    throw new ApiError((body as { detail?: string }).detail || `HTTP ${response.status}`, response.status)
  }
  return body as T
}

// ---------------------------------------------------------------------------
// Types (kontrak endpoint backend — lihat app/main.py)
// ---------------------------------------------------------------------------
export interface DocumentInfo {
  source: string
  chunks: number
  pages: number[]
  category?: string
}

export interface CategoryInfo {
  category: string
  doc_count: number
}

export interface RepeatedQuestion {
  question: string
  count: number
  last_asked: string
}

export interface ReviewCard {
  card_id: string
  question: string
  source: string
  next_due: string
  interval_days: number
  lapses: number
}

export interface WeakSpot {
  topic: string
  score: number
  asked: number
  lapses: number
  wrong: number
}

export interface AnnotationItem {
  chunk_key: string
  note: string
  updated_at: string
}

export interface Session {
  id: string
  title: string
  created_at: string
  updated_at: string
}

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

export interface SessionInfo {
  id: string
  title: string
  messages: number
  tokens_est: number
  over_token_warning?: boolean
}

export interface QuizQuestion {
  question: string
  options: string[]
  answer_index: number
}

export interface QuizHistoryItem {
  source: string
  score: number
  total: number
  created_at: string
}

export interface Flashcard {
  heading: string
  content: string
}

export interface ProgressDoc {
  source: string
  headings_covered: { heading: string; asked: number }[]
  total_questions: number
}

export interface LearningStats {
  total: number
  due_today: number
  avg_lapses: number
}

export interface PrivacyInfo {
  provider_label: string
  external_data_flow: string
  redaction_enabled: boolean
  retention_days: number
  disclosure_text: string
}

export interface GlossaryTerm {
  id: number
  term: string
  definition: string
  source: string
  page: number | null
  category: string
  verified: boolean
  created_at: string
  updated_at: string
}
