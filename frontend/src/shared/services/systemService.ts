import type { PrivacyInfo, RepeatedQuestionItem, SystemMetrics } from '../types'
import { request } from './apiClient'

export const systemService = {
  async getHealth(): Promise<{ status: string }> {
    return request('/health')
  },

  async getMetrics(): Promise<SystemMetrics> {
    return request('/metrics')
  },

  async getAuditLogs(limit = 50): Promise<{ status: string; entries: any[] }> {
    return request(`/audit?limit=${limit}`)
  },

  async getPrivacyInfo(): Promise<PrivacyInfo> {
    return request('/privacy/info')
  },

  async clearUserData(): Promise<{ status: string; deleted: Record<string, number> }> {
    return request('/privacy/data', {
      method: 'DELETE',
    })
  },

  async clearSemanticCache(): Promise<{ status: string; cleared_entries: number }> {
    return request('/privacy/cache', {
      method: 'DELETE',
    })
  },

  async getRepeatedQuestions(days = 7, minHits = 2): Promise<{ status: string; questions: RepeatedQuestionItem[]; usage: any }> {
    return request(`/repeated-questions?days=${days}&min_hits=${minHits}`)
  },
}
