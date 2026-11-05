import { useEffect, useId, useRef } from 'react'
import { X } from '@phosphor-icons/react'
import { SERIES, TRACK } from './theme'

export function Card({ className = '', children, ...rest }) {
  return <section className={`card ${className}`} {...rest}>{children}</section>
}

export function CardHeader({ title, subtitle, action, id }) {
  return (
    <header className="flex items-start justify-between gap-4 px-5 pt-5">
      <div className="min-w-0">
        <h2 id={id} className="text-[17px] font-bold leading-tight">{title}</h2>
        {subtitle && <p className="mt-0.5 text-[13px] text-fg-2">{subtitle}</p>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </header>
  )
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4 pb-6">
      <div className="min-w-0">
        <h1 className="text-[26px] font-extrabold leading-tight sm:text-[30px]">{title}</h1>
        {subtitle && <div className="mt-1 text-sm text-fg-2">{subtitle}</div>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  )
}

/** Selector de opciones excluyentes con esquinas rectas (sin píldoras). */
export function Segmented({ options, value, onChange, label, size = 'md' }) {
  // Con el borde y el padding, el control mide 40 px: la misma altura que .input
  const h = size === 'sm' ? 'h-8 text-[13px]' : 'h-[34px] text-sm'
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-sm border border-line-strong bg-surface p-0.5">
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(o.value)}
            className={`${h} rounded-[4px] px-3 font-semibold transition-colors duration-150 ${
              active ? 'bg-fg text-bg' : 'text-fg-2 hover:bg-hover hover:text-fg'
            }`}
          >
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

/** Anillo de progreso. `pct` puede pasar de 100 (el trazo se limita al círculo). */
export function Ring({ pct, size = 140, stroke = 12, color = SERIES.in, track = TRACK, children, label }) {
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const shown = Math.min(Math.max(pct, 0), 100)
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="img" aria-label={label}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={track} strokeWidth={stroke} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={stroke} strokeLinecap="butt"
          strokeDasharray={c} strokeDashoffset={c * (1 - shown / 100)}
          style={{ transition: 'stroke-dashoffset 400ms ease-out' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">{children}</div>
    </div>
  )
}

/** Mini serie de 24 valores; la hora actual queda marcada. */
export function Sparkline({ values, color = SERIES.in, height = 36, current }) {
  const max = Math.max(1, ...values)
  const w = 120
  const step = w / (values.length - 1 || 1)
  const pts = values.map((v, i) => [i * step, height - 2 - (v / max) * (height - 4)])
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className="h-9 w-full" aria-hidden="true">
      <path d={`${line} L${w},${height} L0,${height} Z`} fill={color} opacity="0.1" />
      <path d={line} fill="none" stroke={color} strokeWidth="1.75" vectorEffect="non-scaling-stroke" />
      {current != null && pts[current] && (
        <circle cx={pts[current][0]} cy={pts[current][1]} r="2.5" fill={color} />
      )}
    </svg>
  )
}

/** Estado como texto con ícono (el color nunca va solo). */
export function StatusText({ icon: Icon, tone = 'text-fg-2', children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-[13px] font-semibold ${tone} ${className}`}>
      {Icon && <Icon size={16} weight="bold" aria-hidden="true" />}
      {children}
    </span>
  )
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      {Icon && <Icon size={32} className="text-fg-3" aria-hidden="true" />}
      <p className="mt-3 font-bold">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-fg-2">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Skeleton({ className = '' }) {
  return <div className={`rounded-sm bg-white/[0.06] ${className}`} aria-hidden="true" />
}

/** Diálogo modal: Escape y clic fuera cierran, el foco entra al abrir y vuelve al cerrar. */
export function Modal({ title, onClose, children, footer, width = 'max-w-lg' }) {
  const titleId = useId()
  const boxRef = useRef(null)

  useEffect(() => {
    const prev = document.activeElement
    const first = boxRef.current?.querySelector('input, select, textarea, button:not([data-close])')
    first?.focus()
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      prev?.focus?.()
    }
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/70 p-0 sm:items-center sm:p-6"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={boxRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`flex max-h-[92dvh] w-full ${width} flex-col rounded-t-lg border border-line-strong bg-surface shadow-float sm:rounded-lg`}
      >
        <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
          <h2 id={titleId} className="text-lg font-bold">{title}</h2>
          <button type="button" data-close className="icon-btn -mr-2" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-4">{footer}</div>}
      </div>
    </div>
  )
}

export function ChartTooltip({ active, payload, label, labelFormatter }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-sm border border-line-strong bg-surface-2 px-3 py-2 text-[13px] shadow-float">
      <p className="mb-1 font-bold">{labelFormatter ? labelFormatter(label) : label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="flex items-center gap-2 text-fg-2">
          <span className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ background: p.color }} />
          {p.name}
          <strong className="num ml-auto pl-4 text-fg">{Number(p.value).toLocaleString('es-PE')}</strong>
        </p>
      ))}
    </div>
  )
}

export function Legend({ items }) {
  return (
    <div className="flex flex-wrap items-center gap-4 text-[13px] text-fg-2">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-[2px]" style={{ background: it.color }} aria-hidden="true" />
          {it.label}
        </span>
      ))}
    </div>
  )
}
