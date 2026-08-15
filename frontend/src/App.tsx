import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { PrivacyNotice } from './components/PrivacyNotice'
import { CommandPaletteProvider } from './context/CommandPaletteContext'
import { SessionsProvider } from './context/SessionsContext'

// Code-splitting: tiap halaman di-load saat dibuka (bundle utama kecil).
const Chat = lazy(() => import('./pages/Chat'))
const Library = lazy(() => import('./pages/Library'))
const Quiz = lazy(() => import('./pages/Quiz'))
const Flashcards = lazy(() => import('./pages/Flashcards'))
const Progress = lazy(() => import('./pages/Progress'))
const Settings = lazy(() => import('./pages/Settings'))
const Glossary = lazy(() => import('./pages/Glossary'))

function Fallback() {
  return <p className="empty-list" style={{ padding: '2rem' }}>Memuat…</p>
}

export default function App() {
  return (
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
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </CommandPaletteProvider>
      <PrivacyNotice />
    </SessionsProvider>
  )
}
