/**
 * Typed API Client Base
 */

export class ApiError extends Error {
  status: number

  constructor(message: string, status = 0) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function dispatchApiError(error?: unknown) {
  window.dispatchEvent(new CustomEvent('kb:api-error', { detail: error }))
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('kb_api_token') || ''
  const headers: Record<string, string> = {
    ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  }

  let response: Response
  try {
    response = await fetch(path, { ...options, headers })
  } catch (error) {
    dispatchApiError(error)
    throw new ApiError('Tidak dapat terhubung ke server backend.', 0)
  }

  let body: any = {}
  try {
    body = await response.json()
  } catch {
    body = {}
  }

  if (!response.ok) {
    dispatchApiError(body)
    const detail = body?.detail || `HTTP ${response.status}: Permintaan gagal.`
    throw new ApiError(detail, response.status)
  }

  return body as T
}
