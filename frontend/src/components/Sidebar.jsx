import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  BarChart2,
  Camera,
  HelpCircle,
  PlusCircle,
  Users,
  Settings,
  Menu,
  ChevronLeft,
  Shield
} from 'lucide-react'
import { useWebSocket } from '../hooks/useWebSocket'

const NAV = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/analytics', icon: BarChart2,        label: 'Analítica & Reportes' },
  { to: '/aforo',     icon: Users,            label: 'Control de Aforo' },
  { to: '/settings',  icon: Settings,         label: 'Ajustes del Sistema' },
]

export default function Sidebar({ collapsed, setCollapsed }) {
  const { connected } = useWebSocket()
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    // Actualizar la hora cada minuto
    const timer = setInterval(() => setNow(new Date()), 60000)
    return () => clearInterval(timer)
  }, [])

  return (
    <aside className={`sidebar ${collapsed ? 'collapsed' : 'expanded'}`}>
      <div className="sidebar-brand" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: collapsed ? 'center' : 'space-between', padding: collapsed ? '1.25rem 0' : '1.25rem 1.25rem 1rem' }}>
        {!collapsed && (
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <div style={{ background: 'var(--teal-dark)', color: 'white', padding: '0.4rem', borderRadius: '8px' }}>
              <Shield size={20} />
            </div>
            <div>
              <div className="sidebar-brand-title">Conteo de Personas</div>
              <div className="sidebar-brand-sub">Sistema de Videovigilancia</div>
            </div>
          </div>
        )}
        <button onClick={() => setCollapsed(!collapsed)} className="btn-ghost" style={{ padding: '0.4rem', marginTop: collapsed ? 0 : '0.2rem' }}>
          {collapsed ? <Menu size={20} /> : <ChevronLeft size={20} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => 
              `nav-item ${collapsed ? 'collapsed' : 'expanded'} ${isActive ? 'active' : ''}`
            }
            title={collapsed ? label : undefined}
          >
            <Icon size={18} className="nav-icon" />
            {!collapsed && <span className="nav-label">{label}</span>}
          </NavLink>
        ))}
      </nav>

      <div className={`sidebar-footer ${collapsed ? 'collapsed' : 'expanded'}`}>
        <div className={`status-pill ${connected ? 'online' : 'offline'}`} style={{ display: 'inline-flex', justifyContent: 'center' }}>
          <span className={`status-dot ${connected ? 'online' : 'offline'}`}></span>
          {!collapsed && <span>{connected ? 'Sistema en Línea' : 'Desconectado'}</span>}
        </div>
        {!collapsed && (
          <div className="status-time">
            Última actualización: {now.toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })}
          </div>
        )}
      </div>
    </aside>
  )
}
