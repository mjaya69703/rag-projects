import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

interface PageHeaderState {
  eyebrow?: string
  title: string
  actions?: ReactNode
}

const PageHeaderContext = createContext<(header: PageHeaderState) => void>(() => {})

/** Halaman mengatur judul + aksi topbar lewat hook ini. */
export function usePageHeader(header: PageHeaderState) {
  const setHeader = useContext(PageHeaderContext)
  useEffect(() => {
    setHeader(header)
  }, [setHeader, header])
}

export function PageHeaderProvider({ children }: { children: ReactNode }) {
  const [header, setHeader] = useState<PageHeaderState>({ title: '' })

  const setHeaderCb = useCallback((h: PageHeaderState) => setHeader(h), [])

  return (
    <PageHeaderContext.Provider value={setHeaderCb}>
      <div className="topbar">
        <div className="topbar-left">
          <div className="crumb">
            <span className="eyebrow">{header.eyebrow || 'KNOWLEDGE BASE'}</span>
            <h1>{header.title}</h1>
          </div>
        </div>
        {header.actions && <div className="topbar-actions">{header.actions}</div>}
      </div>
      {children}
    </PageHeaderContext.Provider>
  )
}
