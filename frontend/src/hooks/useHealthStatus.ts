import { useCallback, useEffect, useRef, useState } from 'react'

export type HealthStatus = 'connecting' | 'connected' | 'degraded' | 'offline'

const POLL_MS = 20_000
const TIMEOUT_MS = 5_000

/**
 * Status kesehatan backend via GET /health.
 * - connecting : pemeriksaan pertama belum selesai
 * - connected  : /health ok
 * - degraded   : /health ok, tapi request aplikasi lain baru saja gagal
 * - offline    : /health gagal
 *
 * Polling tiap 20 detik, dijeda saat tab tersembunyi, dan langsung cek ulang
 * saat tab kembali terlihat. `retry()` dipakai untuk cek ulang manual.
 */
export function useHealthStatus() {
  const [status, setStatus] = useState<HealthStatus>('connecting')
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)
  const lastOkAt = useRef(0)
  const lastApiErrorAt = useRef(0)
  const inFlight = useRef(false)

  const check = useCallback(async () => {
    if (inFlight.current || document.hidden) return
    inFlight.current = true
    const at = new Date()
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
    try {
      const res = await fetch('/health', { cache: 'no-store', signal: controller.signal })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await res.json()
      lastOkAt.current = Date.now()
      // Ada request gagal setelah pemeriksaan sehat terakhir → degraded.
      setStatus(lastApiErrorAt.current > lastOkAt.current ? 'degraded' : 'connected')
    } catch {
      setStatus('offline')
    } finally {
      clearTimeout(timer)
      setCheckedAt(at)
      inFlight.current = false
    }
  }, [])

  // Request aplikasi lain gagal → langsung tandai "degraded" (health tetap ok).
  useEffect(() => {
    const onApiError = () => {
      lastApiErrorAt.current = Date.now()
      setStatus((current) => (current === 'connected' ? 'degraded' : current))
    }
    window.addEventListener('kb:api-error', onApiError)
    return () => window.removeEventListener('kb:api-error', onApiError)
  }, [])

  useEffect(() => {
    void check()
    const id = setInterval(() => void check(), POLL_MS)
    const onVisible = () => {
      if (!document.hidden) void check()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [check])

  return { status, checkedAt, retry: check }
}
