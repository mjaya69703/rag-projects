import React, { createContext, useContext, useEffect, useState } from 'react'
import { request } from '../shared/services/apiClient'
import { useToast } from '../shared/hooks/useToast'

interface PushContextType {
  supported: boolean
  permission: NotificationPermission | 'unsupported'
  isSubscribed: boolean
  remindDue: boolean
  remindHour: number
  loading: boolean
  enable: () => Promise<void>
  disable: () => Promise<void>
  sendTest: () => Promise<void>
  setRemindDue: (value: boolean) => Promise<void>
  setRemindHour: (hour: number) => Promise<void>
}

const PushContext = createContext<PushContextType>({
  supported: false,
  permission: 'unsupported',
  isSubscribed: false,
  remindDue: false,
  remindHour: 7,
  loading: false,
  enable: async () => {},
  disable: async () => {},
  sendTest: async () => {},
  setRemindDue: async () => {},
  setRemindHour: async () => {},
})

function urlBase64ToUint8Array(base64: string): Uint8Array {
  if (!base64 || typeof base64 !== 'string') {
    throw new Error('VAPID Public Key tidak valid dari server.')
  }
  const clean = base64.trim()
  const padding = '='.repeat((4 - (clean.length % 4)) % 4)
  const base64Url = (clean + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64Url)
  const array = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) array[i] = raw.charCodeAt(i)
  return array
}

export function PushProvider({ children }: { children: React.ReactNode }) {
  const { addToast } = useToast()
  const [supported] = useState<boolean>(
    typeof window !== 'undefined' &&
      'serviceWorker' in navigator &&
      'PushManager' in window &&
      'Notification' in window &&
      window.isSecureContext
  )
  const [permission, setPermission] = useState<NotificationPermission | 'unsupported'>(
    supported ? Notification.permission : 'unsupported'
  )
  const [subscription, setSubscription] = useState<PushSubscription | null>(null)
  const [remindDue, setRemindDueState] = useState(false)
  const [remindHour, setRemindHourState] = useState(7)
  const [loading, setLoading] = useState(false)

  const isSubscribed = subscription !== null

  const getEndpoint = () => subscription?.endpoint || ''

  const loadState = async () => {
    if (!supported) return
    try {
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.getSubscription()
      setSubscription(sub)
    } catch {
      // belum terdaftar / tidak didukung
    }
  }

  useEffect(() => {
    loadState()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fetchPublicKey = async (): Promise<string> => {
    const res = await request<{ status: string; public_key: string }>('/push/vapid-public-key')
    if (!res || !res.public_key) {
      throw new Error('Gagal mendapatkan VAPID Public Key dari backend.')
    }
    return res.public_key
  }

  const enable = async () => {
    if (!supported) {
      addToast('Notifikasi web push butuh HTTPS (atau localhost).', 'warning')
      return
    }
    setLoading(true)
    try {
      if (permission !== 'granted') {
        const result = await Notification.requestPermission()
        setPermission(result)
        if (result !== 'granted') {
          addToast('Izin notifikasi ditolak oleh browser.', 'warning')
          return
        }
      }
      const publicKey = await fetchPublicKey()
      const reg = await navigator.serviceWorker.ready
      let sub = await reg.pushManager.getSubscription()
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(publicKey),
        })
      }
      setSubscription(sub)
      const json = sub.toJSON() as { endpoint: string; keys?: { p256dh?: string; auth?: string } }
      await request('/push/subscribe', {
        method: 'POST',
        body: JSON.stringify({
          endpoint: json.endpoint,
          keys: json.keys || {},
          user_agent: navigator.userAgent,
          remind_due: remindDue,
          remind_hour: remindHour,
        }),
      })
      addToast('Notifikasi web push aktif! 🎉', 'success')
    } catch (err: any) {
      addToast(err.message || 'Gagal mengaktifkan notifikasi.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const disable = async () => {
    setLoading(true)
    try {
      const endpoint = getEndpoint()
      if (endpoint) {
        try {
          await request('/push/subscribe', { method: 'DELETE', body: JSON.stringify({ endpoint }) })
        } catch {
          // subscription sudah hilang di server — lanjut
        }
      }
      if (subscription) {
        await subscription.unsubscribe()
        setSubscription(null)
      }
      setRemindDueState(false)
      addToast('Notifikasi web push dimatikan.', 'info')
    } catch (err: any) {
      addToast(err.message || 'Gagal mematikan notifikasi.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const sendTest = async () => {
    if (!isSubscribed) {
      addToast('Aktifkan notifikasi dulu sebelum tes.', 'warning')
      return
    }
    setLoading(true)
    try {
      const res = await request<{ status: string; sent: boolean }>('/push/test', {
        method: 'POST',
        body: JSON.stringify({ endpoint: getEndpoint() }),
      })
      addToast(res.sent ? 'Notifikasi uji terkirim!' : 'Gagal mengirim notifikasi uji.', res.sent ? 'success' : 'error')
    } catch (err: any) {
      addToast(err.message || 'Gagal kirim notifikasi uji.', 'error')
    } finally {
      setLoading(false)
    }
  }

  const setRemindDue = async (value: boolean) => {
    setRemindDueState(value)
    if (isSubscribed) {
      try {
        await request('/push/preferences', {
          method: 'POST',
          body: JSON.stringify({ endpoint: getEndpoint(), remind_due: value }),
        })
        addToast(value ? 'Reminder kartu due diaktifkan.' : 'Reminder kartu due dimatikan.', 'success')
      } catch (err: any) {
        addToast(err.message || 'Gagal simpan preferensi.', 'error')
      }
    }
  }

  const setRemindHour = async (hour: number) => {
    setRemindHourState(hour)
    if (isSubscribed) {
      try {
        await request('/push/preferences', {
          method: 'POST',
          body: JSON.stringify({ endpoint: getEndpoint(), remind_hour: hour }),
        })
        addToast(`Jam pengingat diatur ke ${hour}:00.`, 'success')
      } catch (err: any) {
        addToast(err.message || 'Gagal simpan preferensi.', 'error')
      }
    }
  }

  return (
    <PushContext.Provider
      value={{
        supported,
        permission,
        isSubscribed,
        remindDue,
        remindHour,
        loading,
        enable,
        disable,
        sendTest,
        setRemindDue,
        setRemindHour,
      }}
    >
      {children}
    </PushContext.Provider>
  )
}

export function usePush() {
  return useContext(PushContext)
}
