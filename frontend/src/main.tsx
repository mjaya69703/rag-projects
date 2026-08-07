import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './styles/tokens.css'
import './styles/styles.css'
import App from './App'
import { ToastProvider } from './components/Toast'

// Theme: inisialisasi sebelum render (sesuai localStorage)
document.documentElement.dataset.theme = localStorage.getItem('kb-theme') === 'light' ? 'light' : ''

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <App />
      </ToastProvider>
    </BrowserRouter>
  </StrictMode>,
)
