import type { Message, Session, SourceRef } from '../types'
import { request } from './apiClient'

export interface QueryPayload {
  question: string
  top_k?: number
  source?: string | null
  category?: string | null
  session_id?: string | null
  mode?: 'sliding' | 'summary'
  history_n?: number
}

export interface QueryResult {
  answer: string
  sources: SourceRef[]
  cached?: boolean
  model?: string | null
  session_id?: string
  grounded?: boolean
}

export const chatService = {
  async query(payload: QueryPayload): Promise<QueryResult> {
    return request<QueryResult>('/query', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  async createSession(title = 'New Chat'): Promise<{ status: string; session: Session }> {
    return request('/sessions/create', {
      method: 'POST',
      body: JSON.stringify({ title }),
    })
  },

  async listSessions(): Promise<{ status: string; sessions: Session[] }> {
    return request('/sessions/list')
  },

  async getMessages(sessionId: string): Promise<{ status: string; messages: Message[] }> {
    return request(`/sessions/${encodeURIComponent(sessionId)}/messages`)
  },

  async renameSession(sessionId: string, title: string): Promise<{ status: string }> {
    return request(`/sessions/${encodeURIComponent(sessionId)}/rename`, {
      method: 'PUT',
      body: JSON.stringify({ title }),
    })
  },

  async deleteSession(sessionId: string): Promise<{ status: string }> {
    return request(`/sessions/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
    })
  },
}
