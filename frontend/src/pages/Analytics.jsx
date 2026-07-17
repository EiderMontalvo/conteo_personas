import { useEffect, useRef, useState } from 'react'
import {
  BarChart2, TrendingUp, PieChart as PieIcon,
  CalendarDays, Download, Upload, Search,
  LogIn, LogOut, Clock, Sun, ArrowUpDown,
} from 'lucide-react'
import {
  BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import Topbar from '../components/Topbar'
import { api } from '../hooks/useApi'
import { useToast } from '../context/ToastContext'

//Colores

const DAY_NAMES = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
const DAY_SHORT = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']

const formatHour12 = (h) => `${h % 12 || 12} ${h >= 12 ? 'PM' : 'AM'}`

const formatCompact = (num) => {
  if (num === null || num === undefined) return '—';
  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  if (absNum >= 1000000) return sign + (absNum / 1000000).toFixed(1).replace(/\.0$/, '').replace('.', ',') + 'M';
  if (absNum >= 1000) return sign + (absNum / 1000).toFixed(1).replace(/\.0$/, '').replace('.', ',') + 'k';
  return num.toString();
}

//Custom Tooltip
const CT = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8,
      padding: '8px 12px', boxShadow: '0 4px 12px rgba(0,0,0,.1)', fontSize: 12,
    }}>
      <p style={{ fontWeight: 600, color: '#111827', marginBottom: 4 }}>{label}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.color, margin: '2px 0' }}>
          {p.name}: <strong>{Number(p.value).toLocaleString('es-PE')}</strong>
        </p>
      ))}
    </div>
  )
}

//KPI pequeño
function KpiSm({ label, value, colorClass, sub }) {
  const textColors = { amber: 'var(--amber-dark)', teal: 'var(--teal-dark)', green: 'var(--green)', red: 'var(--red)', purple: 'var(--purple)' }
  return (
    <div className={`kpi-card k-${colorClass}`} style={{ padding: '1.25rem' }}>
      <div className="kpi-body">
        <span className="kpi-label">{label}</span>
        <span className="kpi-value" title={value} style={{ color: textColors[colorClass] || 'var(--text)' }}>{value ?? '—'}</span>
        {sub && <span className="kpi-badge neutral" style={{ marginTop: '0.4rem', alignSelf: 'flex-start' }}>{sub}</span>}
      </div>
    </div>
  )
}
//Mapa de calor
function Heatmap({ data }) {
  if (!data.length) return (
    <p style={{ color: 'var(--text-muted)', fontSize: '.85rem' }}>
      Carga datos para ver el mapa de calor.
    </p>
  )

  const matrix = {}
  const hours = Array.from({ length: 24 }, (_, i) => i)

  data.forEach(e => {
    const d = e.timestamp.slice(0, 10)
    const h = new Date(e.timestamp).getHours()
    if (!matrix[d]) matrix[d] = {}
    matrix[d][h] = (matrix[d][h] || 0) + (e.in_count || 0) + (e.out_count || 0)
  })

  const days = Object.keys(matrix).sort()
  const maxVal = Math.max(1, ...days.flatMap(d => hours.map(h => matrix[d][h] || 0)))

  const cellColor = v => {
    const t = v / maxVal
    return `rgba(13, 148, 136, ${0.15 + t * 0.85})`
  }
  const textColor = v => (v / maxVal) > 0.45 ? '#ffffff' : '#1f2937'

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="cam-table">
        <thead>
          <tr>
            <th>Día</th>
            {hours.map(h => <th key={h}>{formatHour12(h)}</th>)}
          </tr>
        </thead>
        <tbody>
          {days.map(d => {
            const dt = new Date(d + 'T00:00:00')
            return (
              <tr key={d}>
                <td style={{ fontWeight: 600, whiteSpace: 'nowrap' }}>
                  {DAY_SHORT[dt.getDay()]} {d}
                </td>
                {hours.map(h => {
                  const v = matrix[d][h] || 0
                  return (
                    <td
                      key={h}
                      title={`${v} cruces — ${formatHour12(h)}`}
                      style={v > 0 ? { background: cellColor(v), color: textColor(v), fontWeight: 600, textAlign: 'center' } : { textAlign: 'center' }}
                    >
                      {v > 0 ? v : ''}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default function Analytics() {
  const { addToast } = useToast()
  const importRef = useRef(null)

  const [cameras, setCameras] = useState([])
  const [camSel, setCamSel] = useState('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [loading, setLoading] = useState(false)
  const [rows, setRows] = useState([])   // datos cargados
  const [subtitle, setSubtitle] = useState('Selecciona un periodo para analizar')

  //Fechas por defecto
  useEffect(() => {
    const today = new Date()
    const weekAgo = new Date(today)
    weekAgo.setDate(today.getDate() - 7)
    setDateTo(today.toISOString().slice(0, 10))
    setDateFrom(weekAgo.toISOString().slice(0, 10))
  }, [])

  useEffect(() => {
    api.getCameras().then(cams => setCameras(cams)).catch(() => { })
  }, [])

  //Análisis
  const loadData = async () => {
    setLoading(true)
    try {
      const params = {}
      if (camSel.startsWith('cam:')) params.cameraId = camSel.slice(4)
      if (camSel.startsWith('group:')) params.group = camSel.slice(6)

      const json = await api.getHistorical({ ...params, limit: 5000 })
      let data = (json.data || []).filter(e => e.event_type !== 'hourly_heartbeat')
      if (dateFrom) data = data.filter(e => e.timestamp.slice(0, 10) >= dateFrom)
      if (dateTo) data = data.filter(e => e.timestamp.slice(0, 10) <= dateTo)

      if (!data.length) { addToast('Sin datos en el periodo seleccionado', 'warning'); return }

      setRows(data)
      setSubtitle(`${dateFrom} — ${dateTo}  (${data.length} eventos)`)
      addToast(`${data.length} eventos cargados`, 'success')
    } catch (e) {
      addToast('Error al cargar datos: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  //Export
  const exportExcel = () => {
    const params = { dateFrom, dateTo }
    if (camSel.startsWith('cam:')) params.cameraId = camSel.slice(4)
    if (camSel.startsWith('group:')) params.group = camSel.slice(6)
    window.open(api.exportExcelUrl(params), '_blank')
  }

  //Import
  const importExcel = async (file) => {
    if (!file) return
    try {
      addToast('Importando datos…', 'info')
      const json = await api.importExcel(file)
      if (json.ok) addToast(`${json.inserted} registros importados`, 'success')
      else addToast('Error: ' + json.error, 'error')
    } catch (e) {
      addToast('Error al importar: ' + e.message, 'error')
    } finally {
      if (importRef.current) importRef.current.value = ''
    }
  }

  //Métricas derivadas
  const totalIn = rows.reduce((s, e) => s + (e.in_count || 0), 0)
  const totalOut = rows.reduce((s, e) => s + (e.out_count || 0), 0)
  const netFlow = totalIn - totalOut

  //Hora pico
  const byHour = {}
  rows.forEach(e => {
    const h = new Date(e.timestamp).getHours()
    byHour[h] = (byHour[h] || 0) + (e.in_count || 0) + (e.out_count || 0)
  })
  const peakEntry = Object.entries(byHour).sort((a, b) => b[1] - a[1])[0]
  const horaPico = peakEntry ? formatHour12(parseInt(peakEntry[0], 10)) : null

  //Días únicos
  const daysSet = new Set(rows.map(e => e.timestamp.slice(0, 10)))

  //Día más activo
  const byDay = {}
  rows.forEach(e => {
    const d = e.timestamp.slice(0, 10)
    byDay[d] = (byDay[d] || 0) + (e.in_count || 0) + (e.out_count || 0)
  })
  const topDayEntry = Object.entries(byDay).sort((a, b) => b[1] - a[1])[0]
  const topDay = topDayEntry ? (() => {
    const dt = new Date(topDayEntry[0] + 'T00:00:00')
    const dayName = DAY_NAMES[dt.getDay()]
    const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    const dateFormatted = `${dt.getDate()} ${months[dt.getMonth()]} ${dt.getFullYear()}`
    return { name: dayName, date: dateFormatted, count: topDayEntry[1] }
  })() : null

  //Datos para graficos

  //Barras por hora
  const hourBarData = Array.from({ length: 24 }, (_, i) => {
    const insArr = rows.filter(e => new Date(e.timestamp).getHours() === i).reduce((s, e) => s + (e.in_count || 0), 0)
    const outArr = rows.filter(e => new Date(e.timestamp).getHours() === i).reduce((s, e) => s + (e.out_count || 0), 0)
    return { hora: formatHour12(i), Entradas: insArr, Salidas: outArr, total: insArr + outArr }
  })
  const maxHourT = Math.max(...hourBarData.map(d => d.total), 1)

  //Linea diaria
  const lineData = Object.keys(byDay).sort().map(d => ({
    dia: d,
    Total: byDay[d],
    Entradas: rows.filter(e => e.timestamp.slice(0, 10) === d).reduce((s, e) => s + (e.in_count || 0), 0),
    Salidas: rows.filter(e => e.timestamp.slice(0, 10) === d).reduce((s, e) => s + (e.out_count || 0), 0),
  }))

  //Pie
  const pieData = [
    { name: 'Entradas', value: totalIn },
    { name: 'Salidas', value: totalOut },
  ]

  //Por día de la semana (Lun–Dom)
  const byDow = new Array(7).fill(null).map(() => ({ in: 0, out: 0 }))
  rows.forEach(e => {
    const dow = new Date(e.timestamp).getDay()
    byDow[dow].in += e.in_count || 0
    byDow[dow].out += e.out_count || 0
  })
  const dowData = [1, 2, 3, 4, 5, 6, 0].map(i => ({
    dia: DAY_SHORT[i],
    Entradas: byDow[i].in,
    Salidas: byDow[i].out,
    total: byDow[i].in + byDow[i].out,
  }))
  const maxDowT = Math.max(...dowData.map(d => d.total), 1)

  return (
    <>
      <Topbar
        title="Analítica & Reportes"
        subtitle={subtitle}
        connected={true}
        exportParams={{
          dateFrom,
          dateTo,
          ...(camSel.startsWith('cam:') ? { cameraId: camSel.slice(4) } : {}),
          ...(camSel.startsWith('group:') ? { group: camSel.slice(6) } : {})
        }}
      >
        <button type="button" className="btn btn-outline" onClick={() => importRef.current?.click()}>
          <Upload size={14} />
          Importar
        </button>
        <input
          ref={importRef}
          type="file"
          accept=".xlsx"
          style={{ display: 'none' }}
          onChange={e => { importExcel(e.target.files[0]) }}
        />
      </Topbar>

      <div className="page-body">


        <div className="card" style={{ padding: '1.25rem', display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '1.5rem' }}>
          <label className="flex flex-col gap-1.5">
            <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Cámara / Zona</span>
            <select className="select-field min-w-[200px]" value={camSel} onChange={e => setCamSel(e.target.value)}>
              <option value="all">Todas las cámaras</option>
              {cameras.map(c => (
                <option key={c.id} value={`cam:${c.id}`}>{c.name} ({c.role})</option>
              ))}
              {[...new Set(cameras.filter(c => c.group).map(c => c.group))].map(g => (
                <option key={g} value={`group:${g}`}>Grupo: {g}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Desde</span>
            <input
              type="date" className="select-field"
              value={dateFrom} onChange={e => setDateFrom(e.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Hasta</span>
            <input
              type="date" className="select-field"
              value={dateTo} onChange={e => setDateTo(e.target.value)}
            />
          </label>
          <div style={{ marginLeft: 'auto', display: 'flex' }}>
            <button type="button" className="btn btn-success" onClick={loadData} disabled={loading}>
              <Search size={14} />
              {loading ? 'Analizando…' : 'Aplicar filtros'}
            </button>
          </div>
        </div>

        {/*KPIs*/}
        <div className="kpi-grid">
          <KpiSm label="Entradas totales" value={rows.length ? totalIn.toLocaleString('es-PE') : '—'} colorClass="green" sub="Personas" />
          <KpiSm label="Salidas totales" value={rows.length ? totalOut.toLocaleString('es-PE') : '—'} colorClass="red" sub="Personas" />
          <KpiSm label="Flujo neto" value={rows.length ? (netFlow >= 0 ? '+' : '') + netFlow.toLocaleString('es-PE') : '—'} colorClass="teal" sub="Entradas - Salidas" />
          <KpiSm label="Hora pico" value={rows.length && horaPico ? horaPico : '—'} colorClass="amber" sub={horaPico ? `${peakEntry?.[1]} cruces` : ''} />
          <KpiSm label="Día más activo" value={rows.length && topDay ? topDay.name : '—'} colorClass="purple" sub={topDay ? `${topDay.date} / ${topDay.count} cruces` : ''} />
        </div>

        {/*Graficos fila 1: barras hora + línea diaria*/}
        <div className="charts-row cols-1-1">

          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Entradas vs Salidas por Hora
              </span>
            </div>
            <div className="card-body chart-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={hourBarData} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={"var(--grid)"} vertical={false} />
                  <XAxis dataKey="hora" tick={{ fontSize: 10, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={formatCompact} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CT />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Entradas" fill={"var(--teal)"} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Salidas" fill={"var(--amber)"} fillOpacity={.7} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Tráfico Diario
              </span>
            </div>
            <div className="card-body chart-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={lineData} margin={{ top: 5, right: 15, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={"var(--grid)"} />
                  <XAxis dataKey="dia" tick={{ fontSize: 10, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={formatCompact} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CT />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="Entradas" stroke={"var(--teal)"} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                  <Line type="monotone" dataKey="Salidas" stroke={"var(--amber)"} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} strokeDasharray="5 3" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

        {/*Gráficos fila 2: torta + por día de semana*/}
        <div className="charts-row cols-1-1">

          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Proporción Entradas / Salidas
              </span>
            </div>
            <div className="card-body chart-wrap" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={pieData} cx="50%" cy="50%"
                    innerRadius={60} outerRadius={90}
                    paddingAngle={4} dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={{ stroke: '#9ca3af', strokeWidth: 1 }}
                  >
                    <Cell fill={"var(--teal)"} />
                    <Cell fill={"var(--amber)"} />
                  </Pie>
                  <Tooltip content={<CT />} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Actividad por Día de la Semana
              </span>
            </div>
            <div className="card-body chart-wrap">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={dowData} margin={{ top: 5, right: 10, left: -15, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={"var(--grid)"} vertical={false} />
                  <XAxis dataKey="dia" tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={formatCompact} tick={{ fontSize: 11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CT />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="Entradas" fill={"var(--teal)"} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Salidas" fill={"var(--amber)"} fillOpacity={.75} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

        {/*Mapa de calor*/}
        <div className="card">
          <div className="card-header">
            <span className="card-title">
              Mapa de Calor — Actividad por Día y Hora
            </span>
          </div>
          <div className="card-body">
            <Heatmap data={rows} />
          </div>
        </div>



      </div>
    </>
  )
}
