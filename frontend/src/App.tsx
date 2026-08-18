import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { PrivacyNotice } from './components/PrivacyNotice'
import { PWANotifications } from './components/PWANotifications'
import { CommandPaletteProvider } from './context/CommandPaletteContext'
import { PWAProvider } from './context/PWAContext'
import { SessionsProvider } from './context/SessionsContext'

// Code-splitting: tiap halaman di-load saat dibuka (bundle utama kecil).
const Chat = lazy(() => import('./pages/Chat'))
const Library = lazy(() => import('./pages/Library'))
const Quiz = lazy(() => import('./pages/Quiz'))
const Flashcards = lazy(() => import('./pages/Flashcards'))
const Progress = lazy(() => import('./pages/Progress'))
const Settings = lazy(() => import('./pages/Settings'))
const Glossary = lazy(() => import('./pages/Glossary'))
const Annotations = lazy(() => import('./pages/Annotations'))

function Fallback() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', background: 'var(--bg-app)', color: 'var(--text-muted)' }}>
      <div className="spinner-circle" style={{ marginRight: '0.75rem' }} />
      <span style={{ fontSize: '0.88rem', fontWeight: '500' }}>Memuat Studio...</span>
    </div>
  )
}

export default function App() {
  return (
    <PWAProvider>
      <SessionsProvider>
        <CommandPaletteProvider>
          <Suspense fallback={<Fallback />}>
            <Routes>
              <Route element={<AppLayout />}>
                <Route path="/" element={<Chat />} />
                <Route path="/library" element={<Library />} />
                <Route path="/quiz" element={<Quiz />} />
                <Route path="/flashcards" element={<Flashcards />} />
                <Route path="/progress" element={<Progress />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/glossary" element={<Glossary />} />
                <Route path="/annotations" element={<Annotations />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </CommandPaletteProvider>
        <PrivacyNotice />
        <PWANotifications />
      </SessionsProvider>
    </PWAProvider>
  )
}

