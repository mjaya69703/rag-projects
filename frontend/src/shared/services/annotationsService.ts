import type { AnnotationItem } from '../types'
import { request } from './apiClient'

export const annotationsService = {
  async listAnnotations(): Promise<{ status: string; annotations: AnnotationItem[] }> {
    return request('/annotations')
  },

  async upsertNote(chunkKey: string, note: string): Promise<{ status: string; annotation: { chunk_key: string; note: string } }> {
    return request(`/annotations/${encodeURIComponent(chunkKey)}`, {
      method: 'PUT',
      body: JSON.stringify({ note }),
    })
  },

  async deleteNote(chunkKey: string): Promise<{ status: string; chunk_key: string }> {
    return request(`/annotations/${encodeURIComponent(chunkKey)}`, {
      method: 'DELETE',
    })
  },
}