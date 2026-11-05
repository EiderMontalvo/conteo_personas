import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Line, LineChart, Pie, PieChart, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import {
  ArrowDown, ArrowUp, ArrowsClockwise, Broom, CaretLeft, CaretRight, DownloadSimple, Info, MagnifyingGlass, UploadSimple, WarningCircle,
} from '@phosphor-icons/react'
import { api } from '../hooks/useApi'
import { useLive } from '../context/LiveContext'
import { useToast } from '../context/ToastContext'
import {
  daysAgoKey, formatDayKey, formatHour12, formatHourShort, formatNumber, localDayKey, parseDayKey, DAY_NAMES, DAY_SHORT,
} from '../utils/format'
import { Card, CardHeader, ChartTooltip, Legend, Modal, PageHeader, Segmented } from '../components/ui'
import { CATEGORY, CHART_AXIS, CHART_GRID, HEAT, SERIES, CURSOR, TRACK, HEAT_EMPTY } from '../components/theme'

const RANGES = [
  { value: 'today', label: 'Hoy', from: () => localDayKey(), to: () => localDayKey() },
  { value: '7d', label: '7 días', from: () => daysAgoKey(6), to: () => localDayKey() },
  { value: '30d', label: '30 días', from: () => daysAgoKey(29), to: () => localDayKey() },
  { value: 'custom', label: 'Personalizado' },
]
const DOW_ORDER = [1, 2, 3, 4, 5, 6, 0]
const BANDS = [
  { label: 'Madrugada', from: 0, to: 6 },
  { label: 'Mañana', from: 6, to: 12 },
  { label: 'Tarde', from: 12, to: 18 },
  { label: 'Noche', from: 18, to: 24 },
]
const PAGE = 50
const NO_ROWS = []

// Conserva filtros y resultados al cambiar de pantalla y volver.
let cache = null

const shiftDay = (key, days) => {
  const d = parseDayKey(key)
  d.setDate(d.getDate() + days)
  return localDayKey(d)
}
const daysBetween = (a, b) => Math.round((parseDayKey(b) - parseDayKey(a)) / 86400000) + 1

/** Días del periodo, incluidos los que no tienen datos (para que los ejes no salten). */
const dayKeys = (from, to) => {
  const out = []
  for (let k = from; k <= to && out.length < 400; k = shiftDay(k, 1)) out.push(k)
  return out
}

function summarize(rows) {
  const byHour = Array.from({ length: 24 }, () => ({ in: 0, out: 0, max: 0 }))
  const byDay = {}
  const byDow = Array.from({ length: 7 }, () => ({ in: 0, out: 0 }))
  const dowHour = Array.from({ length: 7 }, () => Array(24).fill(0))
  const byCamera = {}
  const bands = BANDS.map(() => 0)
  let totalIn = 0
  let totalOut = 0
  let maxInside = { v: 0, t: null }

  for (const e of rows) {
    const d = new Date(e.timestamp)
    const key = localDayKey(d)
    const h = d.getHours()
    const i = e.in_count || 0
    const o = e.out_count || 0
    const inside = e.people_inside ?? 0
    totalIn += i
    totalOut += o
    byHour[h].in += i
    byHour[h].out += o
    byHour[h].max = Math.max(byHour[h].max, inside)
    byDay[key] ??= { in: 0, out: 0, max: 0 }
    byDay[key].in += i
    byDay[key].out += o
    byDay[key].max = Math.max(byDay[key].max, inside)
    byDow[d.getDay()].in += i
    byDow[d.getDay()].out += o
    dowHour[d.getDay()][h] += i + o
    byCamera[e.camera_id] ??= { in: 0, out: 0 }
    byCamera[e.camera_id].in += i
    byCamera[e.camera_id].out += o
    bands[BANDS.findIndex((b) => h >= b.from && h < b.to)] += i + o
    if (inside > maxInside.v) maxInside = { v: inside, t: e.timestamp }
  }

  const peakHour = byHour.reduce((b, v, h) => (v.in + v.out > b.t ? { h, t: v.in + v.out } : b), { h: null, t: 0 })
  const topDay = Object.entries(byDay).reduce((b, [k, v]) => (v.in + v.out > b.t ? { k, t: v.in + v.out } : b), { k: null, t: 0 })
  return { totalIn, totalOut, byHour, byDay, byDow, dowHour, byCamera, bands, peakHour, topDay, maxInside }
}

function Delta({ now, prev }) {
  if (prev == null) return <span className="text-fg-3">Sin comparación</span>
  if (prev === 0) return <span className="text-fg-2">{now ? 'Sin datos antes para comparar' : 'Igual que antes'}</span>
  const pct = Math.round(((now - prev) / prev) * 100)
  if (pct === 0) return <span className="text-fg-2">Igual que el periodo anterior</span>
  const Icon = pct > 0 ? ArrowUp : ArrowDown
  return (
    <span className="inline-flex items-center gap-1 text-fg-2">
      <Icon size={14} weight="bold" aria-hidden="true" className={pct > 0 ? 'text-accent-strong' : 'text-out'} />
      <span className="num font-semibold text-fg">{Math.abs(pct)} %</span> {pct > 0 ? 'más' : 'menos'} que el periodo anterior
    </span>
  )
}

function Kpi({ label, value, children }) {
  return (
    <Card className="p-4 sm:p-5">
      <p className="eyebrow">{label}</p>
      <p className="display mt-1.5 truncate text-[28px] font-extrabold leading-tight">{value}</p>
      <p className="mt-1 min-h-[20px] text-[13px] leading-5 text-fg-2">{children ?? ' '}</p>
    </Card>
  )
}

function ChartBox({ height = 280, children }) {
  return (
    <div className="px-2 pb-3 pt-4" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer>
    </div>
  )
}

function FlowChart({ rows, stats, days }) {
  const single = days.length <= 1
  const short = days.length > 1 && days.length <= 3
  let data
  let tickFmt
  let tipFmt

  if (single) {
    data = stats.byHour.map((v, h) => ({ x: h, Entradas: v.in, Salidas: v.out }))
    tickFmt = formatHourShort
    tipFmt = (h) => `${formatHour12(h)} – ${formatHour12((h + 1) % 24)}`
  } else if (short) {
    const buckets = {}
    for (const k of days) {
      for (let h = 0; h < 24; h++) {
        const t = parseDayKey(k).getTime() + h * 3600000
        buckets[t] = { x: t, Entradas: 0, Salidas: 0 }
      }
    }
    for (const e of rows) {
      const d = new Date(e.timestamp)
      d.setMinutes(0, 0, 0)
      const b = buckets[d.getTime()]
      if (!b) continue
      b.Entradas += e.in_count || 0
      b.Salidas += e.out_count || 0
    }
    data = Object.values(buckets).sort((a, b) => a.x - b.x)
    tickFmt = (t) => `${DAY_SHORT[new Date(t).getDay()]} ${formatHourShort(new Date(t).getHours())}`
    tipFmt = (t) => `${formatDayKey(localDayKey(new Date(t)))}, ${formatHour12(new Date(t).getHours())}`
  } else {
    data = days.map((k) => ({ x: k, Entradas: stats.byDay[k]?.in ?? 0, Salidas: stats.byDay[k]?.out ?? 0 }))
    tickFmt = formatDayKey
    tipFmt = formatDayKey
  }

  return (
    <Card className="lg:col-span-8">
      <CardHeader
        title={single ? 'Flujo por hora' : short ? 'Flujo hora a hora' : 'Flujo por día'}
        subtitle={single ? 'Entradas y salidas en cada hora del día' : `${days.length} días`}
        action={<Legend items={[{ label: 'Entradas', color: SERIES.in }, { label: 'Salidas', color: SERIES.out }]} />}
      />
      <ChartBox>
        {single ? (
          <AreaChart data={data} margin={{ top: 8, right: 16, left: -6, bottom: 0 }}>
            <CartesianGrid stroke={CHART_GRID} vertical={false} />
            <XAxis dataKey="x" tickFormatter={tickFmt} tick={CHART_AXIS} tickLine={false} axisLine={false} interval={2} />
            <YAxis tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={52} />
            <Tooltip content={<ChartTooltip labelFormatter={tipFmt} />} />
            <Area type="monotone" dataKey="Entradas" stroke={SERIES.in} fill={SERIES.in} fillOpacity={0.1} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Area type="monotone" dataKey="Salidas" stroke={SERIES.out} fill={SERIES.out} fillOpacity={0.06} strokeWidth={2} dot={false} isAnimationActive={false} />
          </AreaChart>
        ) : (
          <LineChart data={data} margin={{ top: 8, right: 16, left: -6, bottom: 0 }}>
            <CartesianGrid stroke={CHART_GRID} vertical={false} />
            <XAxis dataKey="x" tickFormatter={tickFmt} tick={CHART_AXIS} tickLine={false} axisLine={false} minTickGap={28} />
            <YAxis tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={52} />
            <Tooltip content={<ChartTooltip labelFormatter={tipFmt} />} />
            <Line type={short ? 'monotone' : 'linear'} dataKey="Entradas" stroke={SERIES.in} strokeWidth={2} dot={!short && days.length <= 31 && { r: 2.5 }} isAnimationActive={false} />
            <Line type={short ? 'monotone' : 'linear'} dataKey="Salidas" stroke={SERIES.out} strokeWidth={2} dot={!short && days.length <= 31 && { r: 2.5 }} isAnimationActive={false} />
          </LineChart>
        )}
      </ChartBox>
    </Card>
  )
}

function BandsCard({ bands }) {
  const total = bands.reduce((s, v) => s + v, 0)
  const data = BANDS.map((b, i) => ({ name: b.label, value: bands[i], range: `${formatHourShort(b.from)}–${formatHourShort(b.to % 24)}` }))
  const top = data.reduce((m, d) => (d.value > m.value ? d : m), data[0])
  return (
    <Card className="flex flex-col lg:col-span-4">
      <CardHeader title="Franjas del día" subtitle={total ? `La ${top.name.toLowerCase()} concentra el ${Math.round((top.value / total) * 100)} %` : 'Sin cruces en el periodo'} />
      <div className="flex flex-1 flex-wrap items-center gap-4 px-5 pb-5 pt-2">
        <div className="relative h-[170px] w-[170px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={total ? data : [{ name: 'vacío', value: 1 }]} dataKey="value" innerRadius={52} outerRadius={80} paddingAngle={total ? 1.5 : 0} stroke="none" isAnimationActive={false}>
                {total ? data.map((d, i) => <Cell key={d.name} fill={CATEGORY[i]} />) : <Cell fill={TRACK} />}
              </Pie>
              {total > 0 && <Tooltip content={<ChartTooltip />} />}
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="display text-xl font-extrabold">{formatNumber(total)}</span>
            <span className="text-xs text-fg-2">cruces</span>
          </div>
        </div>
        <ul className="min-w-[140px] flex-1 space-y-2 text-sm">
          {data.map((d, i) => (
            <li key={d.name} className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: CATEGORY[i] }} aria-hidden="true" />
              <span className="flex-1">{d.name} <span className="text-fg-3">{d.range}</span></span>
              <span className="num font-semibold">{total ? Math.round((d.value / total) * 100) : 0} %</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  )
}

function MaxOccupancyCard({ stats, days }) {
  const single = days.length <= 1
  const data = single
    ? stats.byHour.map((v, h) => ({ x: h, Máximo: v.max }))
    : days.map((k) => ({ x: k, Máximo: stats.byDay[k]?.max ?? 0 }))
  const { v, t } = stats.maxInside
  return (
    <Card className="lg:col-span-6">
      <CardHeader
        title={single ? 'Máximo de personas dentro, por hora' : 'Máximo de personas dentro, por día'}
        subtitle={t ? `Pico del periodo: ${formatNumber(v)} el ${formatDayKey(localDayKey(new Date(t)))} a las ${new Date(t).toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}` : 'Sin lecturas de aforo'}
      />
      <ChartBox height={240}>
        <BarChart data={data} margin={{ top: 8, right: 16, left: -6, bottom: 0 }}>
          <CartesianGrid stroke={CHART_GRID} vertical={false} />
          <XAxis dataKey="x" tickFormatter={single ? formatHourShort : formatDayKey} tick={CHART_AXIS} tickLine={false} axisLine={false} minTickGap={20} interval={single ? 2 : 'preserveStartEnd'} />
          <YAxis tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={52} />
          <Tooltip cursor={{ fill: CURSOR }} content={<ChartTooltip labelFormatter={single ? (h) => formatHour12(h) : formatDayKey} />} />
          {v > 0 && <ReferenceLine y={v} stroke={SERIES.in} strokeDasharray="4 4" strokeOpacity={0.6} />}
          <Bar dataKey="Máximo" fill={SERIES.out} radius={[2, 2, 0, 0]} maxBarSize={28} isAnimationActive={false} />
        </BarChart>
      </ChartBox>
    </Card>
  )
}

function WeekdayCard({ byDow }) {
  const totals = DOW_ORDER.map((d) => ({ d, in: byDow[d].in, out: byDow[d].out, t: byDow[d].in + byDow[d].out }))
  const max = Math.max(1, ...totals.map((x) => x.t))
  return (
    <Card className="lg:col-span-6">
      <CardHeader title="Por día de la semana" subtitle="Cruces acumulados en el periodo" action={<Legend items={[{ label: 'Entradas', color: SERIES.in }, { label: 'Salidas', color: SERIES.out }]} />} />
      <ul className="space-y-3 px-5 pb-5 pt-5">
        {totals.map(({ d, in: i, out: o, t }) => (
          <li key={d} className="grid grid-cols-[84px_1fr_64px] items-center gap-3 text-sm">
            <span className="text-fg-2">{DAY_NAMES[d]}</span>
            <span className="flex h-3.5 overflow-hidden rounded-[3px] bg-track" aria-hidden="true">
              <span style={{ width: `${(i / max) * 100}%`, background: SERIES.in }} />
              <span style={{ width: `${(o / max) * 100}%`, background: SERIES.out }} />
            </span>
            <span className="num text-right font-semibold">{formatNumber(t)}</span>
            <span className="sr-only">{`${DAY_NAMES[d]}: ${i} entradas, ${o} salidas`}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function CamerasCompare({ byCamera, cameras }) {
  const data = cameras
    .map((c) => ({ name: c.name, Entradas: byCamera[c.camera_id]?.in ?? 0, Salidas: byCamera[c.camera_id]?.out ?? 0 }))
    .sort((a, b) => b.Entradas + b.Salidas - (a.Entradas + a.Salidas))
  return (
    <Card>
      <CardHeader title="Comparación entre cámaras" subtitle="Entradas y salidas de cada cámara en el periodo" action={<Legend items={[{ label: 'Entradas', color: SERIES.in }, { label: 'Salidas', color: SERIES.out }]} />} />
      <ChartBox height={Math.max(160, data.length * 48 + 40)}>
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }} barGap={2}>
          <CartesianGrid stroke={CHART_GRID} horizontal={false} />
          <XAxis type="number" tick={CHART_AXIS} tickLine={false} axisLine={false} allowDecimals={false} />
          <YAxis type="category" dataKey="name" tick={{ ...CHART_AXIS, fill: '#e6e9ee' }} tickLine={false} axisLine={false} width={140} />
          <Tooltip cursor={{ fill: CURSOR }} content={<ChartTooltip />} />
          <Bar dataKey="Entradas" fill={SERIES.in} radius={[0, 2, 2, 0]} maxBarSize={16} isAnimationActive={false} />
          <Bar dataKey="Salidas" fill={SERIES.out} radius={[0, 2, 2, 0]} maxBarSize={16} isAnimationActive={false} />
        </BarChart>
      </ChartBox>
    </Card>
  )
}

function Heatmap({ dowHour }) {
  const max = Math.max(1, ...dowHour.flat())
  return (
    <Card>
      <CardHeader
        title="Patrón semanal"
        subtitle="Cruces por día de la semana y hora, sumando todo el periodo"
        action={
          <div className="flex items-center gap-2 text-xs text-fg-2" aria-hidden="true">
            Menos
            {[0.08, 0.3, 0.55, 0.8, 1].map((a) => <span key={a} className="h-3 w-3 rounded-[2px]" style={{ background: HEAT(a) }} />)}
            Más
          </div>
        }
      />
      <div className="relative overflow-x-auto px-5 pb-5 pt-4">
        <table className="w-full min-w-[760px] table-fixed border-separate" style={{ borderSpacing: 3 }}>
          <thead>
            <tr>
              <th className="w-[92px]"><span className="sr-only">Día</span></th>
              {Array.from({ length: 24 }, (_, h) => (
                <th key={h} scope="col" className="num pb-1 text-center text-[11px] font-medium text-fg-3">
                  {h % 3 === 0 ? formatHourShort(h) : <span className="sr-only">{formatHourShort(h)}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {DOW_ORDER.map((d) => (
              <tr key={d}>
                <th scope="row" className="whitespace-nowrap pr-2 text-left text-[13px] font-medium text-fg-2">{DAY_NAMES[d]}</th>
                {dowHour[d].map((v, h) => (
                  <td
                    key={h}
                    title={`${DAY_NAMES[d]}, ${formatHour12(h)}: ${v} cruces`}
                    className="h-7 rounded-[3px]"
                    style={{ background: v ? HEAT(0.1 + (v / max) * 0.9) : HEAT_EMPTY }}
                  >
                    <span className="sr-only">{v}</span>
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}

function EventsTable({ rows, cameraNames }) {
  const [page, setPage] = useState(0)
  const scrollRef = useRef(null)
  const active = useMemo(
    () => rows.filter((e) => (e.in_count || 0) > 0 || (e.out_count || 0) > 0)
      .sort((a, b) => b.timestamp.localeCompare(a.timestamp)),
    [rows],
  )
  useEffect(() => setPage(0), [rows])
  const pages = Math.max(1, Math.ceil(active.length / PAGE))
  const visible = active.slice(page * PAGE, (page + 1) * PAGE)
  const go = (p) => {
    setPage(p)
    scrollRef.current?.scrollTo({ top: 0 })
  }
  const th = 'sticky top-0 z-10 bg-surface-2 py-2.5 font-semibold shadow-[inset_0_-1px_0_var(--border)]'

  return (
    <Card>
      <CardHeader title="Eventos" subtitle={`${formatNumber(active.length)} cruces en el periodo, del más reciente al más antiguo`} />
      {active.length === 0 ? (
        <p className="px-5 pb-6 pt-4 text-sm text-fg-2">No hay cruces en este periodo.</p>
      ) : (
        <>
          {/* Scroll propio con altura fija: el encabezado queda visible y la página no se alarga */}
          <div ref={scrollRef} className="relative mt-4 max-h-[480px] overflow-auto border-t border-line" tabIndex={0} aria-label="Tabla de eventos">
            <table className="w-full min-w-[640px] border-separate border-spacing-0 text-sm">
              <thead>
                <tr className="text-left text-[13px] text-fg-2">
                  <th scope="col" className={`${th} px-5`}>Fecha y hora</th>
                  <th scope="col" className={`${th} px-3`}>Cámara</th>
                  <th scope="col" className={`${th} px-3 text-right`}>Entradas</th>
                  <th scope="col" className={`${th} px-3 text-right`}>Salidas</th>
                  <th scope="col" className={`${th} px-3 text-right`}>Personas dentro</th>
                  <th scope="col" className={`${th} px-5`}>Origen</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((e) => (
                  <tr key={e.id} className="hover:bg-hover [&>td]:border-b [&>td]:border-line">
                    <td className="num whitespace-nowrap px-5 py-2.5">
                      {new Date(e.timestamp).toLocaleString('es-PE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' })}
                    </td>
                    <td className="px-3 py-2.5">{cameraNames[e.camera_id] ?? `Cámara ${e.camera_id}`}</td>
                    <td className={`num px-3 py-2.5 text-right font-semibold ${e.in_count ? 'text-accent-strong' : 'text-fg-3'}`}>{e.in_count || '—'}</td>
                    <td className={`num px-3 py-2.5 text-right font-semibold ${e.out_count ? 'text-out' : 'text-fg-3'}`}>{e.out_count || '—'}</td>
                    <td className="num px-3 py-2.5 text-right">{e.people_inside}</td>
                    <td className="px-5 py-2.5 text-fg-2">{e.event_type === 'imported' ? 'Importado' : 'Cámara'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-3" aria-label="Páginas de eventos">
            <p className="num text-[13px] text-fg-2">
              {formatNumber(page * PAGE + 1)}–{formatNumber(Math.min((page + 1) * PAGE, active.length))} de {formatNumber(active.length)}
            </p>
            <div className="flex items-center gap-2">
              <button type="button" className="btn-secondary h-8 text-[13px]" onClick={() => go(page - 1)} disabled={page === 0}>
                <CaretLeft size={16} aria-hidden="true" /> Anterior
              </button>
              <span className="num px-1 text-[13px] text-fg-2">Página {page + 1} de {pages}</span>
              <button type="button" className="btn-secondary h-8 text-[13px]" onClick={() => go(page + 1)} disabled={page >= pages - 1}>
                Siguiente <CaretRight size={16} aria-hidden="true" />
              </button>
            </div>
          </nav>
        </>
      )}
    </Card>
  )
}

export default function Analytics() {
  const { cameras } = useLive()
  const { addToast } = useToast()
  const importRef = useRef(null)
  const reqId = useRef(0)

  const [range, setRange] = useState(cache?.range ?? '7d')
  const [dateFrom, setDateFrom] = useState(cache?.dateFrom ?? daysAgoKey(6))
  const [dateTo, setDateTo] = useState(cache?.dateTo ?? localDayKey())
  const [camSel, setCamSel] = useState(cache?.camSel ?? 'all')
  const [result, setResult] = useState(cache?.result ?? null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [available, setAvailable] = useState(null)
  const [confirmPurge, setConfirmPurge] = useState(false)

  useEffect(() => {
    cache = { range, dateFrom, dateTo, camSel, result }
  }, [range, dateFrom, dateTo, camSel, result])

  const loadRange = () => api.getHistoricalRange().then((r) => setAvailable(r?.data ?? null)).catch(() => {})

  const filterParams = (from, to, sel = camSel) => {
    const p = { dateFrom: from, dateTo: to }
    if (sel.startsWith('cam:')) p.cameraId = Number(sel.slice(4))
    if (sel.startsWith('zone:')) p.group = sel.slice(5)
    return p
  }

  const analyze = async (from = dateFrom, to = dateTo, sel = camSel) => {
    if (!from || !to || from > to) {
      setError('Revisa las fechas: la inicial debe ser anterior o igual a la final.')
      return
    }
    const id = ++reqId.current
    const len = daysBetween(from, to)
    const prevFrom = shiftDay(from, -len)
    const prevTo = shiftDay(from, -1)
    setLoading(true)
    setError(null)
    try {
      const clean = (json) => (json?.data ?? []).filter((e) => e.event_type !== 'hourly_heartbeat')
      const [cur, prev] = await Promise.all([
        api.getHistorical({ ...filterParams(from, to, sel), limit: 100000 }),
        api.getHistorical({ ...filterParams(prevFrom, prevTo, sel), limit: 100000 }).catch(() => null),
      ])
      if (id !== reqId.current) return // llegó una respuesta vieja
      const prevRows = prev ? clean(prev) : null
      setResult({
        from, to, rows: clean(cur),
        prev: prevRows && { from: prevFrom, to: prevTo, in: prevRows.reduce((s, e) => s + (e.in_count || 0), 0), out: prevRows.reduce((s, e) => s + (e.out_count || 0), 0) },
      })
    } catch (e) {
      if (id === reqId.current) setError(`No se pudieron cargar los datos: ${e.message}`)
    } finally {
      if (id === reqId.current) setLoading(false)
    }
  }

  useEffect(() => {
    loadRange()
    if (!cache?.result) analyze()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const pickRange = (value) => {
    setRange(value)
    const r = RANGES.find((x) => x.value === value)
    if (!r?.from) return
    const from = r.from()
    const to = r.to()
    setDateFrom(from)
    setDateTo(to)
    analyze(from, to)
  }

  const exportExcel = async () => {
    try {
      addToast('Preparando el Excel…', 'info')
      await api.exportExcel(filterParams(dateFrom, dateTo))
    } catch (e) {
      addToast(`No se pudo exportar: ${e.message}`, 'error')
    }
  }

  const importExcel = async (file) => {
    if (!file) return
    try {
      addToast('Importando…', 'info')
      const json = await api.importExcel(file)
      const d = json?.data ?? {}
      const errs = d.errors?.length ? `, ${d.errors.length} filas con error` : ''
      addToast(`${d.inserted ?? 0} registros nuevos y ${d.updated ?? 0} actualizados${errs}`, d.errors?.length ? 'warning' : 'success')
      loadRange()
      analyze()
    } catch (e) {
      addToast(`No se pudo importar: ${e.message}`, 'error')
    } finally {
      if (importRef.current) importRef.current.value = ''
    }
  }

  const purge = async () => {
    setConfirmPurge(false)
    try {
      const json = await api.purgeDuplicates()
      const n = json?.data?.deleted ?? 0
      addToast(n ? `${n} registros importados duplicados eliminados` : 'No había duplicados', n ? 'success' : 'info')
      if (n) analyze()
    } catch (e) {
      addToast(`No se pudo limpiar: ${e.message}`, 'error')
    }
  }

  const rows = result?.rows ?? NO_ROWS
  const stats = useMemo(() => summarize(rows), [rows])
  const days = useMemo(() => (result ? dayKeys(result.from, result.to) : []), [result])
  const cameraNames = Object.fromEntries(cameras.map((c) => [c.camera_id, c.name]))
  const zones = [...new Set(cameras.map((c) => c.zone).filter(Boolean))]
  const shownCameras = camSel === 'all' ? cameras : cameras.filter((c) => (camSel.startsWith('zone:') ? c.zone === camSel.slice(5) : `cam:${c.camera_id}` === camSel))
  const net = stats.totalIn - stats.totalOut
  const prev = result?.prev

  return (
    <>
      <PageHeader
        title="Analítica"
        subtitle={available?.first_date ? `Hay datos del ${formatDayKey(available.first_date)} al ${formatDayKey(available.last_date)}` : 'Flujo de personas por periodo'}
      >
        <button type="button" className="btn-secondary" onClick={exportExcel}>
          <DownloadSimple size={18} aria-hidden="true" /> Exportar
        </button>
        <button type="button" className="btn-secondary" onClick={() => importRef.current?.click()}>
          <UploadSimple size={18} aria-hidden="true" /> Importar
        </button>
        <button type="button" className="btn-ghost" onClick={() => setConfirmPurge(true)}>
          <Broom size={18} aria-hidden="true" /> Limpiar duplicados
        </button>
        <input ref={importRef} type="file" accept=".xlsx,.xlsm" className="hidden" onChange={(e) => importExcel(e.target.files[0])} />
      </PageHeader>

      <Card className="mb-5 p-4 sm:p-5">
        <form
          className="grid grid-cols-1 items-end gap-x-4 gap-y-3 sm:grid-cols-2 xl:grid-cols-[auto_minmax(132px,160px)_minmax(132px,160px)_minmax(150px,1fr)_auto]"
          onSubmit={(e) => { e.preventDefault(); setRange('custom'); analyze() }}
        >
          <div className="min-w-0 sm:col-span-2 xl:col-span-1">
            <span className="field-label">Periodo</span>
            <Segmented options={RANGES.map(({ value, label }) => ({ value, label }))} value={range} onChange={pickRange} label="Periodo" />
          </div>
          <label className="min-w-0">
            <span className="field-label">Desde</span>
            <input type="date" className="input" value={dateFrom} max={dateTo} onChange={(e) => { setDateFrom(e.target.value); setRange('custom') }} />
          </label>
          <label className="min-w-0">
            <span className="field-label">Hasta</span>
            <input type="date" className="input" value={dateTo} min={dateFrom} onChange={(e) => { setDateTo(e.target.value); setRange('custom') }} />
          </label>
          <label className="min-w-0">
            <span className="field-label">Cámara o zona</span>
            <select className="input" value={camSel} onChange={(e) => { setCamSel(e.target.value); analyze(dateFrom, dateTo, e.target.value) }}>
              <option value="all">Todas las cámaras</option>
              {cameras.map((c) => <option key={c.id} value={`cam:${c.camera_id}`}>{c.name}</option>)}
              {zones.map((z) => <option key={z} value={`zone:${z}`}>Zona {z}</option>)}
            </select>
          </label>
          {/* El texto no cambia al cargar (solo el ícono), así el botón conserva su ancho */}
          <button type="submit" className="btn-primary h-10 w-full xl:w-[124px]" disabled={loading} aria-busy={loading}>
            {loading ? <ArrowsClockwise size={18} className="animate-spin" aria-hidden="true" /> : <MagnifyingGlass size={18} aria-hidden="true" />}
            Analizar
          </button>
        </form>
        <p className="mt-3 min-h-[20px] text-[13px] leading-5" role={error ? 'alert' : undefined}>
          {error ? (
            <span className="inline-flex items-center gap-1.5 text-danger"><WarningCircle size={16} weight="bold" aria-hidden="true" />{error}</span>
          ) : result ? (
            <span className="text-fg-2">
              Mostrando {result.from === result.to ? formatDayKey(result.from) : `${formatDayKey(result.from)} – ${formatDayKey(result.to)}`}
              {prev && <> · comparado con {prev.from === prev.to ? formatDayKey(prev.from) : `${formatDayKey(prev.from)} – ${formatDayKey(prev.to)}`}</>}
              {loading && ' · actualizando…'}
            </span>
          ) : null}
        </p>
      </Card>

      <div className={`space-y-4 transition-opacity duration-150 lg:space-y-5 ${loading ? 'opacity-60' : ''}`} aria-busy={loading}>
        {result && rows.length === 0 && (
          <p className="flex items-center gap-2 rounded-md border border-line bg-surface px-4 py-3 text-sm text-fg-2">
            <Info size={18} className="shrink-0 text-fg-3" aria-hidden="true" />
            No hay cruces en este periodo.{available?.last_date && ` El último dato es del ${formatDayKey(available.last_date)}.`}
          </p>
        )}

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 lg:gap-5">
          <Kpi label="Entradas" value={formatNumber(stats.totalIn)}>{result && <Delta now={stats.totalIn} prev={prev?.in} />}</Kpi>
          <Kpi label="Salidas" value={formatNumber(stats.totalOut)}>{result && <Delta now={stats.totalOut} prev={prev?.out} />}</Kpi>
          <Kpi label="Balance" value={`${net > 0 ? '+' : ''}${formatNumber(net)}`}>
            {net === 0 ? 'Entradas y salidas iguales' : net > 0 ? 'Entró más gente' : 'Salió más gente'}
          </Kpi>
          <Kpi label="Hora pico" value={stats.peakHour.h == null ? '—' : formatHour12(stats.peakHour.h)}>
            {stats.peakHour.h != null && `${formatNumber(stats.peakHour.t)} cruces en esa hora`}
          </Kpi>
          <Kpi label="Día más activo" value={stats.topDay.k ? DAY_NAMES[parseDayKey(stats.topDay.k).getDay()] : '—'}>
            {stats.topDay.k && `${formatDayKey(stats.topDay.k)} · ${formatNumber(stats.topDay.t)} cruces`}
          </Kpi>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-5">
          <FlowChart rows={rows} stats={stats} days={days} />
          <BandsCard bands={stats.bands} />
          <MaxOccupancyCard stats={stats} days={days} />
          <WeekdayCard byDow={stats.byDow} />
        </div>

        {shownCameras.length > 1 && <CamerasCompare byCamera={stats.byCamera} cameras={shownCameras} />}
        <Heatmap dowHour={stats.dowHour} />
        <EventsTable rows={rows} cameraNames={cameraNames} />
      </div>

      {confirmPurge && (
        <Modal
          title="Limpiar duplicados importados"
          onClose={() => setConfirmPurge(false)}
          width="max-w-md"
          footer={
            <>
              <button type="button" className="btn-secondary" onClick={() => setConfirmPurge(false)}>Cancelar</button>
              <button type="button" className="btn-danger" onClick={purge}>Eliminar duplicados</button>
            </>
          }
        >
          <p className="text-sm text-fg-2">
            Se borran los registros importados desde Excel que estén repetidos (misma cámara y mismo instante, al segundo).
            Los conteos de las cámaras no se tocan. No se puede deshacer.
          </p>
        </Modal>
      )}
    </>
  )
}
