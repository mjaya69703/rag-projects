import React, { createContext, useContext, useEffect, useState } from 'react'

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[]
  readonly userChoice: Promise<{
    outcome: 'accepted' | 'dismissed'
    platform: string
  }>
  prompt(): Promise<void>
}

interface PWAContextType {
  isInstallable: boolean
  isInstalled: boolean
  isOffline: boolean
  isIOS: boolean
  promptInstall: () => Promise<boolean>
  swUpdateAvailable: boolean
  applyUpdate: () => void
  showInstallGuide: boolean
  setShowInstallGuide: (show: boolean) => void
}

const PWAContext = createContext<PWAContextType>({
  isInstallable: false,
  isInstalled: false,
  isOffline: false,
  isIOS: false,
  promptInstall: async () => false,
  swUpdateAvailable: false,
  applyUpdate: () => {},
  showInstallGuide: false,
  setShowInstallGuide: () => {},
})

export function PWAProvider({ children }: { children: React.ReactNode }) {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null)
  const [isInstallable, setIsInstallable] = useState(false)
  const [isInstalled, setIsInstalled] = useState(false)
  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  const [swUpdateAvailable, setSwUpdateAvailable] = useState(false)
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(null)
  const [showInstallGuide, setShowInstallGuide] = useState(false)

  const isIOS =
    typeof navigator !== 'undefined' &&
    (/iPad|iPhone|iPod/.test(navigator.userAgent) ||
      (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1))

  useEffect(() => {
    // Check if app is launched in standalone mode
    const isStandalone =
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as any).standalone === true
    setIsInstalled(isStandalone)

    // Online / Offline listeners
    const handleOnline = () => setIsOffline(false)
    const handleOffline = () => setIsOffline(true)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // beforeinstallprompt listener (Chromium / Android)
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault()
      setDeferredPrompt(e as BeforeInstallPromptEvent)
      setIsInstallable(true)
    }
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt)

    // appinstalled listener
    const handleAppInstalled = () => {
      setIsInstalled(true)
      setIsInstallable(false)
      setDeferredPrompt(null)
    }
    window.addEventListener('appinstalled', handleAppInstalled)

    // Listen for custom SW update event dispatched from main.tsx
    const handleSWUpdate = (e: CustomEvent<{ worker: ServiceWorker }>) => {
      setSwUpdateAvailable(true)
      if (e.detail?.worker) {
        setWaitingWorker(e.detail.worker)
      }
    }
    window.addEventListener('sw-update-available' as any, handleSWUpdate as any)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt)
      window.removeEventListener('appinstalled', handleAppInstalled)
      window.removeEventListener('sw-update-available' as any, handleSWUpdate as any)
    }
  }, [])

  const promptInstall = async (): Promise<boolean> => {
    if (deferredPrompt) {
      try {
        await deferredPrompt.prompt()
        const choice = await deferredPrompt.userChoice
        if (choice.outcome === 'accepted') {
          setIsInstalled(true)
          setIsInstallable(false)
          setDeferredPrompt(null)
          return true
        }
      } catch {
        // user dismissed or prompt failed
      }
      return false
    }

    // If on iOS, open the manual installation guide modal
    if (isIOS && !isInstalled) {
      setShowInstallGuide(true)
      return true
    }

    return false
  }

  const applyUpdate = () => {
    if (waitingWorker) {
      waitingWorker.postMessage({ type: 'SKIP_WAITING' })
      window.location.reload()
    }
  }

  return (
    <PWAContext.Provider
      value={{
        isInstallable,
        isInstalled,
        isOffline,
        isIOS,
        promptInstall,
        swUpdateAvailable,
        applyUpdate,
        showInstallGuide,
        setShowInstallGuide,
      }}
    >
      {children}
    </PWAContext.Provider>
  )
}

export function usePWA() {
  return useContext(PWAContext)
}
