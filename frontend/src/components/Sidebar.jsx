import { NavLink } from 'react-router-dom'
import { Gauge, ChartLineUp, UsersThree, GearSix, SidebarSimple, X, VideoCamera } from '@phosphor-icons/react'
import { useLive } from '../context/LiveContext'

const NAV = [
  { to: '/', icon: Gauge, label: 'Monitoreo' },
  { to: '/analytics', icon: ChartLineUp, label: 'Analítica' },
  { to: '/aforo', icon: UsersThree, label: 'Aforo' },
  { to: '/settings', icon: GearSix, label: 'Ajustes' },
]

function SystemStatus({ collapsed }) {
  const { wsConnected, cameras, status } = useLive()
  const total = cameras.length
  const online = cameras.filter((c) => status[c.camera_id]?.state === 'connected').length
  const demo = cameras.some((c) => status[c.camera_id]?.demo)
  const healthy = wsConnected && total > 0 && online === total

  const line = !wsConnected
    ? 'Sin conexión con el servidor'
    : total === 0
      ? 'Sin cámaras configuradas'
      : `${online} de ${total} cámara${total === 1 ? '' : 's'} en línea`

  return (
    <div className={`border-t border-white/10 ${collapsed ? 'px-2 py-4' : 'px-4 py-4'}`} aria-live="polite">
      <div className={`flex items-center gap-2.5 ${collapsed ? 'justify-center' : ''}`} title={collapsed ? line : undefined}>
        <span
          className={`inline-block h-2 w-2 shrink-0 rounded-[2px] ${healthy ? 'bg-[#3fbf8a]' : 'bg-[#f0a43a]'}`}
          aria-hidden="true"
        />
        {!collapsed && <span className="text-[13px] font-semibold text-ink-fg">{line}</span>}
      </div>
      {!collapsed && demo && (
        <p className="mt-1.5 pl-[18px] text-xs text-ink-muted">Modo demo: datos simulados</p>
      )}
    </div>
  )
}

export default function Sidebar({ collapsed, onToggle, mobileOpen, onCloseMobile }) {
  const width = collapsed ? 'lg:w-[76px]' : 'lg:w-[248px]'

  return (
    <>
      {mobileOpen && (
        <div className="fixed inset-0 z-30 bg-black/70 lg:hidden" onClick={onCloseMobile} aria-hidden="true" />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-[264px] flex-col border-r border-line bg-ink text-ink-fg transition-transform duration-200 lg:sticky lg:top-0 lg:h-dvh lg:translate-x-0 lg:transition-[width] ${width} ${
          mobileOpen ? 'visible translate-x-0' : 'invisible -translate-x-full lg:visible'
        }`}
        aria-label="Navegación principal"
      >
        <div className={`flex items-center gap-3 px-4 pb-6 pt-5 ${collapsed ? 'lg:justify-center lg:px-2' : ''}`}>
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent-strong">
            <VideoCamera size={20} weight="fill" className="text-on-accent" aria-hidden="true" />
          </div>
          <div className={`min-w-0 flex-1 ${collapsed ? 'lg:hidden' : ''}`}>
            <p className="truncate text-[15px] font-bold leading-tight" style={{ fontStretch: '112%' }}>Conteo de personas</p>
            <p className="truncate text-xs text-ink-muted">Analítica de video</p>
          </div>
          <button type="button" className="icon-btn text-ink-muted hover:bg-white/10 hover:text-ink-fg lg:hidden" onClick={onCloseMobile} aria-label="Cerrar menú">
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onCloseMobile}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `flex h-11 items-center gap-3 rounded-md px-3 text-[15px] font-semibold transition-colors duration-150 ${
                  collapsed ? 'lg:justify-center lg:px-0' : ''
                } ${isActive ? 'bg-white/[0.08] text-ink-fg' : 'text-ink-muted hover:bg-white/[0.05] hover:text-ink-fg'}`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={20} weight={isActive ? 'fill' : 'regular'} aria-hidden="true" className={`shrink-0 ${isActive ? 'text-accent' : ''}`} />
                  <span className={collapsed ? 'lg:sr-only' : ''}>{label}</span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="hidden px-3 pb-2 lg:block">
          <button
            type="button"
            onClick={onToggle}
            className={`flex h-10 w-full items-center gap-3 rounded-md px-3 text-[13px] font-semibold text-ink-muted transition-colors duration-150 hover:bg-white/[0.07] hover:text-ink-fg ${collapsed ? 'justify-center px-0' : ''}`}
            aria-label={collapsed ? 'Expandir menú' : 'Contraer menú'}
          >
            <SidebarSimple size={20} aria-hidden="true" />
            {!collapsed && 'Contraer'}
          </button>
        </div>

        <SystemStatus collapsed={collapsed} />
      </aside>
    </>
  )
}
