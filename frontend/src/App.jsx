// src/App.jsx
import { useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './context/ToastContext'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Analytics from './pages/Analytics'
import CapacityControl from './pages/CapacityControl'
import Settings from './pages/Settings'

export default function App() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <ToastProvider>
      <div className={`layout ${collapsed ? 'collapsed' : 'expanded'}`}>
        <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
        <div className="main-wrap" style={{ minWidth: 0, overflowX: 'hidden' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/aforo" element={<CapacityControl />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </div>
    </ToastProvider>
  )
}
