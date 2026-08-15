import type { DocumentInfo } from '../types'
import { request } from './apiClient'

export const documentService = {
  async listDocuments(): Promise<{ status: string; documents: DocumentInfo[] }> {
    return request('/documents')
  },

  async uploadFile(file: File, source?: string, category?: string): Promise<{ status: string; job_id: string; source: string }> {
    const formData = new FormData()
    formData.append('file', file)
    if (source) formData.append('source', source)
    if (category) formData.append('category', category)

    return request('/upload', {
      method: 'POST',
      body: formData,
    })
  },

  async ingestUrl(url: string, source?: string, category?: string): Promise<{ status: string; job_id: string; source: string }> {
    return request('/ingest-url', {
      method: 'POST',
      body: JSON.stringify({ url, source, category }),
    })
  },

  async deleteDocument(source: string, purge = false): Promise<{ status: string; deleted_chunks: number }> {
    return request(`/documents/${encodeURIComponent(source)}?purge=${purge}`, {
      method: 'DELETE',
    })
  },

  async setCategory(source: string, category: string): Promise<{ status: string; source: string; category: string }> {
    return request(`/documents/${encodeURIComponent(source)}/category`, {
      method: 'PUT',
      body: JSON.stringify({ category }),
    })
  },

  async listCategories(): Promise<{ status: string; categories: Record<string, string> }> {
    return request('/categories')
  },

  async getLocations(query: string): Promise<{ status: string; query: string; locations: any[] }> {
    return request(`/locations?q=${encodeURIComponent(query)}`)
  },
}
