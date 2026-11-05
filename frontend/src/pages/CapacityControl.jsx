import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { SignIn, SignOut, UsersThree } from '@phosphor-icons/react'
import { api } from '../hooks/useApi'
import { useLive } from '../context/LiveContext'
import { agruparPorZona, estadoAforo } from '../utils/capacity'
import { formatNumber } from '../utils/format'
import { Card, EmptyState, PageHeader, Ring, Skeleton, StatusText } from '../components/ui'
import { capacityMeta } from '../components/theme'

const ORDER = { 'Crítico': 0, Advertencia: 1, Normal: 2 }

function SpaceCard({ space }) {
  const meta = capacityMeta(space.status)
  const over = space.people_inside - space.max_capacity
  return (
    <Card className="flex flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-[17px] font-bold">{space.name}</h2>
          <p className="text-[13px] text-fg-2">
            {space.esGrupo ? `Zona con ${space.cameraIds.length} cámaras` : 'Una cámara'}
          </p>
        </div>
        <StatusText icon={meta.icon} tone={meta.cls}>{space.status}</StatusText>
      </div>

      <div className="mt-5 flex items-center gap-5">
        <Ring pct={space.pct} size={112} stroke={11} color={meta.ring} label={`Ocupación ${space.pct} %`}>
          <span className="display text-[24px] font-extrabold leading-none">{space.pct}%</span>
        </Ring>
        <div className="min-w-0">
          <p className="display text-[32px] font-extrabold leading-none">
            {formatNumber(space.people_inside)}
            <span className="ml-1 text-base font-semibold text-fg-2" style={{ fontStretch: '100%' }}>/ {formatNumber(space.max_capacity)}</span>
          </p>
          <p className="mt-1.5 text-[13px] text-fg-2">
            {over > 0 ? `${formatNumber(over)} por encima del límite` : `${formatNumber(space.available)} lugares libres`}
          </p>
        </div>
      </div>

      <div className="mt-5 flex gap-5 border-t border-line pt-4 text-[13px]">
        <span className="inline-flex items-center gap-1.5 text-fg-2">
          <SignIn size={16} className="text-accent-strong" aria-hidden="true" />
          <span className="num font-semibold text-fg">{formatNumber(space.total_in)}</span> entradas hoy
        </span>
        <span className="inline-flex items-center gap-1.5 text-fg-2">
          <SignOut size={16} className="text-out" aria-hidden="true" />
          <span className="num font-semibold text-fg">{formatNumber(space.total_out)}</span> salidas hoy
        </span>
      </div>
    </Card>
  )
}

export default function CapacityControl() {
  const { cameras, states, loaded } = useLive()
  const [thresholds, setThresholds] = useState({ warning: 80, critical: 100 })

  useEffect(() => {
    api.getSettings()
      .then((r) => r?.data && setThresholds({ warning: r.data.warning_threshold, critical: r.data.critical_threshold }))
      .catch(() => {})
  }, [])

  const spaces = cameras.filter((c) => c.role === 'space').map((c) => ({ ...c, ...states[c.camera_id] }))
  const groups = agruparPorZona(spaces)
    .map((g) => ({ ...g, ...estadoAforo(g.people_inside, g.max_capacity, thresholds.warning, thresholds.critical) }))
    .sort((a, b) => ORDER[a.status] - ORDER[b.status] || b.pct - a.pct)

  const count = (s) => groups.filter((g) => g.status === s).length
  const people = groups.reduce((s, g) => s + g.people_inside, 0)

  return (
    <>
      <PageHeader
        title="Aforo"
        subtitle={`Advertencia desde ${thresholds.warning} % y crítico desde ${thresholds.critical} % del límite. Los más ocupados primero.`}
      >
        <Link to="/settings" className="btn-secondary">Cambiar umbrales</Link>
      </PageHeader>

      {!loaded ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-[240px]" />)}
        </div>
      ) : groups.length === 0 ? (
        <Card>
          <EmptyState
            icon={UsersThree}
            title="No hay espacios de aforo"
            action={<Link to="/settings" className="btn-primary">Ir a Ajustes</Link>}
          >
            Crea o edita una cámara con el tipo “Espacio de aforo” y un límite de personas para verla aquí.
          </EmptyState>
        </Card>
      ) : (
        <>
          <dl className="mb-5 grid grid-cols-2 overflow-hidden rounded-lg border border-line bg-surface sm:grid-cols-4">
            {[
              ['Personas dentro', formatNumber(people), ''],
              ['Normales', count('Normal'), 'text-ok'],
              ['En advertencia', count('Advertencia'), 'text-warn'],
              ['Críticos', count('Crítico'), 'text-danger'],
            ].map(([label, value, tone], i) => (
              <div key={label} className={`px-5 py-4 ${i ? 'border-line sm:border-l' : ''} ${i === 2 ? 'border-t sm:border-t-0' : ''} ${i === 3 ? 'border-l border-t sm:border-t-0' : ''} ${i === 1 ? 'border-l' : ''}`}>
                <dt className="eyebrow">{label}</dt>
                <dd className={`display mt-1 text-[28px] font-extrabold leading-tight ${tone}`}>{value}</dd>
              </div>
            ))}
          </dl>
          <div className="grid gap-4 sm:grid-cols-2 lg:gap-5 xl:grid-cols-3">
            {groups.map((g) => <SpaceCard key={g.key} space={g} />)}
          </div>
        </>
      )}
    </>
  )
}
