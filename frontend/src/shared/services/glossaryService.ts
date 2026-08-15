import type { GlossaryTerm, MindmapNode } from '../types'
import { request } from './apiClient'

export const glossaryService = {
  async listGlossary(
    search = '',
    source?: string | null,
    verified?: boolean | null
  ): Promise<{ status: string; terms: GlossaryTerm[] }> {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (source) params.set('source', source)
    if (verified !== undefined && verified !== null) params.set('verified', String(verified))
    return request(`/glossary?${params.toString()}`)
  },

  async createTerm(term: Partial<GlossaryTerm>): Promise<{ status: string; term: GlossaryTerm }> {
    return request('/glossary', {
      method: 'POST',
      body: JSON.stringify(term),
    })
  },

  async updateTerm(id: number, term: Partial<GlossaryTerm>): Promise<{ status: string; term: GlossaryTerm }> {
    return request(`/glossary/${id}`, {
      method: 'PUT',
      body: JSON.stringify(term),
    })
  },

  async toggleVerify(id: number): Promise<{ status: string; term: GlossaryTerm }> {
    return request(`/glossary/${id}/verify`, {
      method: 'PUT',
    })
  },

  async deleteTerm(id: number): Promise<{ status: string; term_id: number }> {
    return request(`/glossary/${id}`, {
      method: 'DELETE',
    })
  },

  async getCandidates(source?: string | null, limit = 10): Promise<{ status: string; candidates: GlossaryTerm[] }> {
    const params = new URLSearchParams()
    if (source) params.set('source', source)
    params.set('limit', String(limit))
    return request(`/glossary/candidates?${params.toString()}`)
  },

  async getMindmap(source?: string | null): Promise<{ status: string; mindmap: MindmapNode }> {
    const query = source ? `?source=${encodeURIComponent(source)}` : ''
    return request(`/learning/mindmap${query}`)
  },

  async getDocumentSummary(source: string): Promise<{ status: string; source: string; summary: string }> {
    return request(`/learning/summary?source=${encodeURIComponent(source)}`)
  },
}
