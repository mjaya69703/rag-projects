import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/tokens.css'
import './styles/styles.css'
import App from './App'
import { PushProvider } from './context/PushContext'
import { ToastProvider } from './shared/hooks'

// Theme: inisialisasi sebelum render (sesuai localStorage)
const savedTheme = localStorage.getItem('kb_theme') || localStorage.getItem('kb-theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
document.documentElement.setAttribute('data-theme', savedTheme)
document.documentElement.dataset.theme = savedTheme

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <PushProvider>
          <App />
        </PushProvider>
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
)

// Register PWA Service Worker
if ('serviceWorker' in navigator && !import.meta.env.DEV) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((reg) => {
        // Detect update
        reg.addEventListener('updatefound', () => {
          const newWorker = reg.installing
          if (newWorker) {
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                window.dispatchEvent(
                  new CustomEvent('sw-update-available', { detail: { worker: newWorker } })
                )
              }
            })
          }
        })
      })
      .catch((err) => {
        console.warn('Service Worker registration failed:', err)
      })
  })
}

