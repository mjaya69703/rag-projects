import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/tokens.css'
import './styles/styles.css'
import App from './App'
import { ToastProvider } from './shared/hooks'

// Theme: inisialisasi sebelum render (sesuai localStorage)
const savedTheme = localStorage.getItem('kb_theme') || localStorage.getItem('kb-theme') || (window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark')
document.documentElement.setAttribute('data-theme', savedTheme)
document.documentElement.dataset.theme = savedTheme

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <App />
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
)
