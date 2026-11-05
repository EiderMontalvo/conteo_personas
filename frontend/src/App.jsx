import { Suspense, lazy, useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { List } from '@phosphor-icons/react'
import { ToastProvider } from './context/ToastContext'
import { LiveProvider } from './context/LiveContext'
import Sidebar from './components/Sidebar'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Analytics = lazy(() => import('./pages/Analytics'))
const CapacityControl = lazy(() => import('./pages/CapacityControl'))
const Settings = lazy(() => import('./pages/Settings'))

const readCollapsed = () => {
  try { return localStorage.getItem('sidebar-collapsed') === '1' } catch { return false }
}

export default function App() {
  const [collapsed, setCollapsed] = useState(readCollapsed)
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  useEffect(() => {
    try { localStorage.setItem('sidebar-collapsed', collapsed ? '1' : '0') } catch { /* sin almacenamiento */ }
  }, [collapsed])

  // Al cambiar de pantalla, el foco va al contenido para lectores de pantalla
  useEffect(() => {
    document.getElementById('main')?.focus({ preventScroll: true })
    window.scrollTo(0, 0)
  }, [location.pathname])

  return (
    <ToastProvider>
      <LiveProvider>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-sm focus:bg-surface focus:px-3 focus:py-2">
          Ir al contenido
        </a>
        <div className="lg:flex">
          <Sidebar
            collapsed={collapsed}
            onToggle={() => setCollapsed((c) => !c)}
            mobileOpen={mobileOpen}
            onCloseMobile={() => setMobileOpen(false)}
          />
          <div className="min-w-0 flex-1">
            <div className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-bg/95 px-4 backdrop-blur lg:hidden">
              <button type="button" className="icon-btn -ml-2" onClick={() => setMobileOpen(true)} aria-label="Abrir menú">
                <List size={22} />
              </button>
              <span className="font-bold" style={{ fontStretch: '112%' }}>Conteo de personas</span>
            </div>
            <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1440px] px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
              <Suspense fallback={<p className="py-16 text-center text-sm text-fg-2">Cargando…</p>}>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/analytics" element={<Analytics />} />
                <Route path="/aforo" element={<CapacityControl />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
              </Suspense>
            </main>
          </div>
        </div>
      </LiveProvider>
    </ToastProvider>
  )
}
