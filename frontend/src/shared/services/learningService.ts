import type {
  AIFlashcard,
  CardStats,
  DocumentProgress,
  Flashcard,
  FlashcardStat,
  MasteryStat,
  QuizAttempt,
  QuizAttemptDetail,
  QuizGradeResult,
  QuizScoreItem,
  RecommendationItem,
  ReviewCard,
  WeakSpot,
} from '../types'
import { request } from './apiClient'

export const learningService = {
  // Spaced repetition & Review cards
  async getDueCards(source?: string | null, limit = 20): Promise<{ status: string; cards: ReviewCard[]; stats: CardStats }> {
    const params = new URLSearchParams()
    if (source) params.set('source', source)
    params.set('limit', String(limit))
    return request(`/learning/due?${params.toString()}`)
  },

  async listCards(source?: string | null, limit = 100): Promise<{ status: string; cards: ReviewCard[]; stats: CardStats }> {
    const params = new URLSearchParams()
    if (source) params.set('source', source)
    params.set('limit', String(limit))
    return request(`/learning/cards?${params.toString()}`)
  },

  async answerCard(cardId: string, ratingOrRemembered: number | boolean): Promise<{ status: string; card: ReviewCard }> {
    const body: Record<string, any> = { card_id: cardId }
    if (typeof ratingOrRemembered === 'boolean') {
      body.remembered = ratingOrRemembered
    } else {
      body.rating = ratingOrRemembered
    }
    return request('/learning/answer', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },

  async generateFlashcards(
    source?: string | null,
    n = 5,
    saveToDeck = true
  ): Promise<{ status: string; source?: string | null; cards: AIFlashcard[]; saved_cards: ReviewCard[] }> {
    return request('/learning/flashcards/generate', {
      method: 'POST',
      body: JSON.stringify({ source, n, save_to_deck: saveToDeck }),
    })
  },

  async createCustomCard(
    question: string,
    answer: string,
    source?: string | null
  ): Promise<{ status: string; card: ReviewCard }> {
    return request('/learning/flashcards/custom', {
      method: 'POST',
      body: JSON.stringify({ question, answer, source }),
    })
  },

  async deleteCard(cardId: string): Promise<{ status: string; card_id: string }> {
    return request(`/learning/flashcards/${encodeURIComponent(cardId)}`, {
      method: 'DELETE',
    })
  },

  // Quizzes
  async generateQuiz(source?: string | null, n = 5, topic?: string | null): Promise<{ status: string } & QuizAttempt> {
    return request('/learning/quiz/generate', {
      method: 'POST',
      body: JSON.stringify({ source, n, topic: topic || null }),
    })
  },

  async gradeQuiz(attemptId: string, answers: number[]): Promise<{ status: string; saved_cards: ReviewCard[] } & QuizGradeResult> {
    return request('/learning/quiz/grade', {
      method: 'POST',
      body: JSON.stringify({ attempt_id: attemptId, answers }),
    })
  },

  async getQuizHistory(limit = 10, offset = 0): Promise<{
    status: string
    history: QuizScoreItem[]
    total?: number
  }> {
    return request(`/learning/quiz/history?limit=${limit}&offset=${offset}`)
  },

  async getQuizAttempt(attemptId: string): Promise<{ status: string } & QuizAttemptDetail> {
    return request(`/learning/quiz/attempts/${encodeURIComponent(attemptId)}`)
  },

  // Fallback Chunk Flashcards
  async getFlashcards(source?: string | null, limit = 20): Promise<{ status: string; cards: Flashcard[] }> {
    const query = source ? `?source=${encodeURIComponent(source)}&limit=${limit}` : `?limit=${limit}`
    return request(`/learning/flashcards${query}`)
  },

  async answerFlashcard(heading: string, source: string, known: boolean): Promise<{ status: string; stat: FlashcardStat }> {
    return request('/learning/flashcards/answer', {
      method: 'POST',
      body: JSON.stringify({ heading, source, known }),
    })
  },

  async getFlashcardStats(limit = 50): Promise<{ status: string; stats: FlashcardStat[] }> {
    return request(`/learning/flashcards/stats?limit=${limit}`)
  },

  // Weak-spots & Progress & Recommendations
  async getWeakSpots(limit = 8): Promise<{ status: string; weak_spots: WeakSpot[]; mastery?: MasteryStat[] }> {
    return request(`/learning/weak-spots?limit=${limit}`)
  },

  async getMastery(): Promise<{ status: string; mastery: MasteryStat[] }> {
    return request('/learning/mastery')
  },

  async getProgress(): Promise<{ status: string; progress: DocumentProgress[] }> {
    return request('/learning/progress')
  },

  async getRecommendations(): Promise<{
    status: string
    card_stats: CardStats
    recommendations: RecommendationItem[]
    mastery_summary: MasteryStat[]
    weak_spots: WeakSpot[]
  }> {
    return request('/learning/recommendations')
  },

  // Export data belajar (backup portabel)
  async exportLearningData(): Promise<{ status: string; exported_at: string; [key: string]: any }> {
    return request('/learning/export')
  },
}
