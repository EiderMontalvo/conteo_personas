import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { DownloadSimple, SignIn, SignOut, VideoCamera, WifiSlash, Pulse, UsersThree } from '@phosphor-icons/react'
import { api } from '../hooks/useApi'
import { useLive } from '../context/LiveContext'
import { useToast } from '../context/ToastContext'
import { agruparPorZona, estadoAforo } from '../utils/capacity'
import {
  daysAgoKey, formatAgo, formatDayKey, formatHour12, formatHourShort, formatLongDate, formatNumber, formatTime,
  localDayKey, parseDayKey, DAY_SHORT,
} from '../utils/format'
import { Card, CardHeader, ChartTooltip, EmptyState, Legend, PageHeader, Ring, Segmented, Sparkline, StatusText } from '../components/ui'
import { SERIES, CHART_AXIS, CHART_GRID, STATUS_COLORS, capacityMeta, REF_LINE, CURSOR } from '../components/theme'
import { connectionMeta } from '../components/connection'
import LiveVideo from '../components/LiveVideo'

function useNow(intervalMs = 5000) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(t)
  }, [intervalMs])
  return now
}

function useThresholds() {
  const [t, setT] = useState({ warning: 80, critical: 100 })
  useEffect(() => {
    api.getSettings()
      .then((res) => res?.data && setT({ warning: res.data.warning_threshold, critical: res.data.critical_threshold }))
      .catch(() => {})
  }, [])
  return t
}

/** Personas dentro del grupo a lo largo del día: suma la última lectura de cada cámara, un punto por minuto. */
function groupOccupancy(occupancy, cameraIds, now) {
  const events = cameraIds.flatMap((id) => (occupancy[id] ?? []).map((p) => ({ ...p, id })))
  events.sort((a, b) => a.t - b.t)
  const last = {}
  const byMinute = new Map()
  for (const e of events) {
    last[e.id] = e.v
    const minute = Math.floor(e.t / 60000) * 60000
    byMinute.set(minute, Object.values(last).reduce((s, v) => s + v, 0))
  }
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  const points = [{ t: start.getTime(), v: 0 }, ...[...byMinute].map(([t, v]) => ({ t, v }))]
  points.push({ t: now, v: points[points.length - 1].v })
  return points
}

function CameraAlert({ cameras, status }) {
  const down = cameras.filter((c) => status[c.camera_id]?.state === 'reconnecting')
  if (!down.length) return null
  return (
    <div role="alert" className="mb-5 flex flex-wrap items-start gap-3 rounded-md border border-danger/25 bg-danger-soft px-4 py-3">
      <WifiSlash size={20} weight="bold" className="mt-0.5 shrink-0 text-danger" aria-hidden="true" />
      <div className="min-w-0 flex-1 text-sm">
        {down.map((c) => {
          const s = status[c.camera_id]
          return (
            <p key={c.camera_id}>
              <strong>{c.name}</strong> no está contando: {s.last_error || 'sin respuesta'}.
              {s.next_retry_at && <span className="text-fg-2"> Reintento a las {formatTime(s.next_retry_at, true)}.</span>}
            </p>
          )
        })}
        <p className="mt-1 text-fg-2">Los cruces que ocurran mientras tanto no se registran.</p>
      </div>
      <Link to="/settings" className="btn-secondary h-8 text-[13px]">Revisar cámaras</Link>
    </div>
  )
}

function VideoCard({ cameras, status, states }) {
  const [selected, setSelected] = useState(null)
  const cam = cameras.find((c) => c.id === selected) ?? cameras[0]
  if (!cam) {
    return (
      <Card className="lg:col-span-8">
        <EmptyState icon={VideoCamera} title="Sin cámaras" action={<Link to="/settings" className="btn-primary">Agregar cámara</Link>}>
          Agrega una cámara para ver su video y sus conteos aquí.
        </EmptyState>
      </Card>
    )
  }
  const st = states[cam.camera_id] ?? {}
  return (
    <Card className="p-3 lg:col-span-8">
      {cameras.length > 1 && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 px-1">
          <h2 className="text-[15px] font-bold">Video en vivo</h2>
          {cameras.length <= 4 ? (
            <Segmented size="sm" label="Cámara" value={cam.id} onChange={setSelected}
              options={cameras.map((c) => ({ value: c.id, label: c.name }))} />
          ) : (
            <select className="input h-8 w-auto text-[13px]" value={cam.id} onChange={(e) => setSelected(Number(e.target.value))} aria-label="Cámara">
              {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
        </div>
      )}
      <LiveVideo camera={cam} connection={status[cam.camera_id]} totals={{ in: st.total_in ?? 0, out: st.total_out ?? 0 }} />
    </Card>
  )
}

function OccupancyCard({ group, thresholds, loaded }) {
  if (!loaded) return <Card className="min-h-[220px]" />
  if (!group) {
    return (
      <Card>
        <EmptyState icon={UsersThree} title="Sin espacio que medir">Configura una cámara para ver el aforo.</EmptyState>
      </Card>
    )
  }
  const { pct, available, status } = estadoAforo(group.people_inside, group.max_capacity, thresholds.warning, thresholds.critical)
  const meta = capacityMeta(status)
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[17px] font-bold">Aforo actual</h2>
          <p className="truncate text-[13px] text-fg-2">{group.esGrupo ? `Zona ${group.name}` : group.name}</p>
        </div>
        <StatusText icon={meta.icon} tone={meta.cls}>{status}</StatusText>
      </div>
      <div className="mt-4 flex items-center gap-5">
        <Ring pct={pct} size={124} stroke={12} color={meta.ring} label={`Ocupación ${pct} %`}>
          <span className="display text-[28px] font-extrabold leading-none">{pct}%</span>
          <span className="mt-0.5 text-xs text-fg-2">ocupado</span>
        </Ring>
        <dl className="min-w-0 flex-1 space-y-2.5">
          <div>
            <dt className="text-[13px] text-fg-2">Personas dentro</dt>
            <dd className="display text-[30px] font-extrabold leading-tight">{formatNumber(group.people_inside)}</dd>
          </div>
          <div className="flex gap-5">
            <div>
              <dt className="text-[13px] text-fg-2">Límite</dt>
              <dd className="num font-bold">{formatNumber(group.max_capacity)}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-fg-2">Libres</dt>
              <dd className="num font-bold">{formatNumber(available)}</dd>
            </div>
          </div>
        </dl>
      </div>
    </Card>
  )
}

function MiniStat({ label, icon: Icon, value, detail, series, color, currentHour }) {
  return (
    <Card className="flex flex-col p-4">
      <div className="flex items-center justify-between">
        <span className="eyebrow">{label}</span>
        <Icon size={18} className="text-fg-3" aria-hidden="true" />
      </div>
      <p className="display mt-1.5 text-[28px] font-extrabold leading-none">{value}</p>
      <p className="mt-1.5 text-[13px] text-fg-2">{detail}</p>
      <div className="mt-auto pt-3"><Sparkline values={series} color={color} current={currentHour} /></div>
    </Card>
  )
}

function OccupancyTimeline({ occupancy, group, thresholds, now }) {
  const points = useMemo(
    () => (group ? groupOccupancy(occupancy, group.cameraIds, now) : []),
    [occupancy, group, now],
  )
  const cap = group?.max_capacity ?? 0
  const warnAt = Math.round((cap * thresholds.warning) / 100)
  const peak = points.reduce((m, p) => (p.v > m.v ? p : m), { v: 0, t: null })
  const start = new Date(now)
  start.setHours(0, 0, 0, 0)
  const yMax = Math.max(cap * 1.1, peak.v * 1.1, 10)

  return (
    <Card className="lg:col-span-8">
      <CardHeader
        title="Personas dentro durante el día"
        subtitle={peak.t ? `Máximo de hoy: ${formatNumber(peak.v)} a las ${formatTime(peak.t)}` : 'Sin movimiento todavía'}
        action={<Legend items={[{ label: 'Personas dentro', color: SERIES.in }, { label: 'Límite', color: STATUS_COLORS.danger }, { label: 'Advertencia', color: STATUS_COLORS.warn }]} />}
      />
      <div className="h-[260px] px-2 pb-3 pt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 8, right: 16, left: -6, bottom: 0 }}>
            <CartesianGrid stroke={CHART_GRID} vertical={false} />
            <XAxis
              dataKey="t" type="number" scale="time" domain={[start.getTime(), start.getTime() + 86400000]}
              ticks={Array.from({ length: 9 }, (_, i) => start.getTime() + i * 3 * 3600000)}
              tickFormatter={(t) => formatHourShort(new Date(t).getHours())}
              tick={CHART_AXIS} tickLine={false} axisLine={false}
            />
            <YAxis domain={[0, Math.ceil(yMax)]} tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={52} />
            <Tooltip content={<ChartTooltip labelFormatter={(t) => formatTime(t)} />} />
            {cap > 0 && <ReferenceLine y={cap} stroke={STATUS_COLORS.danger} strokeDasharray="5 4" />}
            {cap > 0 && <ReferenceLine y={warnAt} stroke={STATUS_COLORS.warn} strokeDasharray="5 4" />}
            <Area type="stepAfter" dataKey="v" name="Personas dentro" stroke={SERIES.in} fill={SERIES.in} fillOpacity={0.12} strokeWidth={2} dot={false} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function CamerasCard({ cameras, states, status, now }) {
  return (
    <Card className="flex flex-col lg:col-span-4">
      <CardHeader title="Cámaras" subtitle="Conexión y conteo de hoy" action={<Link to="/settings" className="btn-ghost h-8 px-2.5 text-[13px]">Gestionar</Link>} />
      {cameras.length === 0 ? (
        <EmptyState icon={VideoCamera} title="Ninguna cámara">Configúralas en Ajustes.</EmptyState>
      ) : (
        <ul className="mt-3 divide-y divide-line">
          {cameras.map((c) => {
            const conn = status[c.camera_id]
            const meta = connectionMeta(conn)
            const st = states[c.camera_id] ?? {}
            const seen = st.lastSeen ? formatAgo(now - st.lastSeen) : null
            return (
              <li key={c.camera_id} className="px-5 py-3.5">
                <div className="flex items-center justify-between gap-3">
                  <p className="min-w-0 truncate font-semibold">{c.name}</p>
                  <StatusText icon={meta.icon} tone={meta.tone}>{meta.label}</StatusText>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-fg-2">
                  <span className="num">{formatNumber(st.total_in)} entradas · {formatNumber(st.total_out)} salidas</span>
                  {seen && <span>Último cruce {seen}</span>}
                </div>
                {conn?.state === 'reconnecting' && conn.last_error && (
                  <p className="mt-1 text-[13px] text-danger">{conn.last_error}</p>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

const hourRange = (h) => `${formatHour12(h)} – ${formatHour12((h + 1) % 24)}`

function HourlyFlow({ hourly }) {
  const hourNow = new Date().getHours()
  const data = hourly.map((h, i) => ({ hora: i, Entradas: h.in, Salidas: h.out }))
  const peak = hourly.reduce((b, h, i) => (h.in + h.out > b.t ? { h: i, t: h.in + h.out } : b), { h: null, t: 0 })
  return (
    <Card className="lg:col-span-6">
      <CardHeader
        title="Entradas y salidas por hora"
        subtitle={peak.h == null ? 'Aún no hay cruces hoy' : `Hora pico: ${formatHour12(peak.h)} con ${formatNumber(peak.t)} cruces`}
        action={<Legend items={[{ label: 'Entradas', color: SERIES.in }, { label: 'Salidas', color: SERIES.out }]} />}
      />
      <div className="h-[240px] px-2 pb-3 pt-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, left: -6, bottom: 0 }} barGap={1}>
            <CartesianGrid stroke={CHART_GRID} vertical={false} />
            <XAxis dataKey="hora" tickFormatter={formatHourShort} tick={CHART_AXIS} tickLine={false} axisLine={false} interval={2} />
            <YAxis tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={52} />
            <Tooltip cursor={{ fill: CURSOR }} content={<ChartTooltip labelFormatter={hourRange} />} />
            <ReferenceLine x={hourNow} stroke={REF_LINE} strokeOpacity={0.3} />
            <Bar dataKey="Entradas" fill={SERIES.in} radius={[2, 2, 0, 0]} isAnimationActive={false} />
            <Bar dataKey="Salidas" fill={SERIES.out} radius={[2, 2, 0, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function NetFlow({ hourly }) {
  const data = hourly.map((h, i) => ({ hora: i, Neto: h.in - h.out }))
  const net = data.reduce((s, d) => s + d.Neto, 0)
  return (
    <Card className="lg:col-span-6">
      <CardHeader
        title="Balance por hora"
        subtitle={`Entradas menos salidas. En el día: ${net > 0 ? '+' : ''}${formatNumber(net)}`}
        action={<Legend items={[{ label: 'Entra más gente', color: SERIES.in }, { label: 'Sale más gente', color: SERIES.out }]} />}
      />
      <div className="h-[240px] px-2 pb-3 pt-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, left: -6, bottom: 0 }}>
            <CartesianGrid stroke={CHART_GRID} vertical={false} />
            <XAxis dataKey="hora" tickFormatter={formatHourShort} tick={CHART_AXIS} tickLine={false} axisLine={false} interval={2} />
            <YAxis tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={52} />
            <ReferenceLine y={0} stroke={REF_LINE} strokeOpacity={0.35} />
            <Tooltip cursor={{ fill: CURSOR }} content={<ChartTooltip labelFormatter={hourRange} />} />
            <Bar dataKey="Neto" name="Balance" radius={[2, 2, 2, 2]} isAnimationActive={false}>
              {data.map((d) => <Cell key={d.hora} fill={d.Neto >= 0 ? SERIES.in : SERIES.out} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

function WeekCard({ hourly }) {
  const [days, setDays] = useState(null)
  useEffect(() => {
    api.getHistorical({ dateFrom: daysAgoKey(6), limit: 100000 })
      .then((json) => {
        const acc = {}
        for (const e of json?.data ?? []) {
          if (e.event_type === 'hourly_heartbeat') continue
          const k = localDayKey(new Date(e.timestamp))
          acc[k] ??= { in: 0, out: 0 }
          acc[k].in += e.in_count || 0
          acc[k].out += e.out_count || 0
        }
        setDays(acc)
      })
      .catch(() => setDays({}))
  }, [])

  const today = localDayKey()
  const todayTotals = hourly.reduce((s, h) => ({ in: s.in + h.in, out: s.out + h.out }), { in: 0, out: 0 })
  const data = Array.from({ length: 7 }, (_, i) => {
    const key = daysAgoKey(6 - i)
    const v = key === today ? todayTotals : days?.[key] ?? { in: 0, out: 0 }
    return { key, dia: DAY_SHORT[parseDayKey(key).getDay()], Entradas: v.in, Salidas: v.out }
  })

  return (
    <Card className="lg:col-span-7">
      <CardHeader
        title="Últimos 7 días"
        subtitle="Entradas y salidas por día"
        action={<Legend items={[{ label: 'Entradas', color: SERIES.in }, { label: 'Salidas', color: SERIES.out }]} />}
      />
      <div className="h-[250px] px-2 pb-3 pt-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 16, left: -6, bottom: 0 }} barGap={3}>
            <CartesianGrid stroke={CHART_GRID} vertical={false} />
            <XAxis dataKey="dia" tick={CHART_AXIS} tickLine={false} axisLine={false} />
            <YAxis tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={52} />
            <Tooltip cursor={{ fill: CURSOR }} content={<ChartTooltip />} />
            <Bar dataKey="Entradas" fill={SERIES.in} radius={[3, 3, 0, 0]} maxBarSize={22} isAnimationActive={false} />
            <Bar dataKey="Salidas" fill={SERIES.out} radius={[3, 3, 0, 0]} maxBarSize={22} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="sr-only">
        {data.map((d) => `${formatDayKey(d.key)}: ${d.Entradas} entradas, ${d.Salidas} salidas.`).join(' ')}
      </p>
    </Card>
  )
}

function ActivityCard({ events, wsConnected }) {
  return (
    <Card className="flex flex-col lg:col-span-5">
      <CardHeader title="Actividad reciente" subtitle="Cruces recibidos desde que abriste esta página" />
      {events.length === 0 ? (
        <EmptyState icon={Pulse} title={wsConnected ? 'Esperando cruces' : 'Sin conexión con el servidor'}>
          {wsConnected
            ? 'Cada vez que alguien cruce la línea de una cámara aparecerá aquí.'
            : 'Revisa que el backend esté corriendo en el puerto 8000.'}
        </EmptyState>
      ) : (
        <ol className="mt-3 max-h-[262px] divide-y divide-line overflow-y-auto">
          {events.map((e) => (
            <li key={e.id} className="flex items-center gap-3 px-5 py-2.5 text-sm">
              <span className="num w-[64px] shrink-0 text-fg-2">{formatTime(e.timestamp, true)}</span>
              <span className="min-w-0 flex-1 truncate">{e.camera_name}</span>
              {e.in_count > 0 && (
                <span className="num inline-flex items-center gap-1 font-semibold text-accent-strong">
                  <SignIn size={15} aria-hidden="true" />+{e.in_count}<span className="sr-only">entradas</span>
                </span>
              )}
              {e.out_count > 0 && (
                <span className="num inline-flex items-center gap-1 font-semibold text-out">
                  <SignOut size={15} aria-hidden="true" />−{e.out_count}<span className="sr-only">salidas</span>
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </Card>
  )
}

export default function Dashboard() {
  const { cameras, loaded, states, status, hourly, occupancy, events, wsConnected, lastMessageAt } = useLive()
  const { addToast } = useToast()
  const thresholds = useThresholds()
  const now = useNow()
  const [groupKey, setGroupKey] = useState(null)

  const groups = useMemo(
    () => agruparPorZona(cameras.map((c) => ({ ...c, ...states[c.camera_id] }))),
    [cameras, states],
  )
  const group = groups.find((g) => g.key === groupKey) ?? groups[0]

  const totals = cameras.reduce(
    (s, c) => ({ in: s.in + (states[c.camera_id]?.total_in ?? 0), out: s.out + (states[c.camera_id]?.total_out ?? 0) }),
    { in: 0, out: 0 },
  )
  const hourNow = new Date().getHours()

  const exportToday = async () => {
    try {
      addToast('Preparando el Excel de hoy…', 'info')
      await api.exportExcel({ dateFrom: localDayKey(), dateTo: localDayKey() })
    } catch (e) {
      addToast(`No se pudo exportar: ${e.message}`, 'error')
    }
  }

  const liveLine = !wsConnected
    ? 'Sin conexión en vivo con el servidor'
    : lastMessageAt
      ? `Último cruce ${formatAgo(now - lastMessageAt)}`
      : 'En vivo, esperando cruces'

  return (
    <>
      <PageHeader
        title="Monitoreo"
        subtitle={<span>{formatLongDate()} <span aria-hidden="true">·</span> {liveLine}</span>}
      >
        {groups.length > 1 && (
          <label className="flex items-center gap-2 text-sm">
            <span className="text-fg-2">Espacio</span>
            <select className="input h-9 w-auto min-w-[180px]" value={group?.key ?? ''} onChange={(e) => setGroupKey(e.target.value)}>
              {groups.map((g) => <option key={g.key} value={g.key}>{g.esGrupo ? `Zona ${g.name}` : g.name}</option>)}
            </select>
          </label>
        )}
        <button type="button" className="btn-secondary" onClick={exportToday}>
          <DownloadSimple size={18} aria-hidden="true" /> Exportar hoy
        </button>
      </PageHeader>

      <CameraAlert cameras={cameras} status={status} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
        <VideoCard cameras={cameras} status={status} states={states} />
        <div className="flex flex-col gap-4 lg:col-span-4 lg:gap-5">
          <OccupancyCard group={group} thresholds={thresholds} loaded={loaded} />
          <div className="grid flex-1 grid-cols-2 gap-4 lg:gap-5">
            <MiniStat
              label="Entradas hoy" icon={SignIn} value={formatNumber(totals.in)}
              detail={`${formatNumber(hourly[hourNow].in)} esta hora`}
              series={hourly.map((h) => h.in)} color={SERIES.in} currentHour={hourNow}
            />
            <MiniStat
              label="Salidas hoy" icon={SignOut} value={formatNumber(totals.out)}
              detail={`${formatNumber(hourly[hourNow].out)} esta hora`}
              series={hourly.map((h) => h.out)} color={SERIES.out} currentHour={hourNow}
            />
          </div>
        </div>

        <OccupancyTimeline occupancy={occupancy} group={group} thresholds={thresholds} now={now} />
        <CamerasCard cameras={cameras} states={states} status={status} now={now} />
        <HourlyFlow hourly={hourly} />
        <NetFlow hourly={hourly} />
        <WeekCard hourly={hourly} />
        <ActivityCard events={events} wsConnected={wsConnected} />
      </div>
    </>
  )
}
