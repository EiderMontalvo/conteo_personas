// src/pages/Dashboard.jsx
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  LogIn, LogOut, Users, Clock, CalendarDays,
  Video, AlertTriangle, TrendingUp, TrendingDown, Minus,
  Activity, Wifi,
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar,
  PieChart, Pie, Cell, Tooltip, Legend,
  XAxis, YAxis, CartesianGrid, ResponsiveContainer,
} from 'recharts'
import Topbar from '../components/Topbar'
import { useWebSocket } from '../hooks/useWebSocket'
import { api } from '../hooks/useApi'

// ─── Paleta ──────────────────────────────────────────────────

const TOOLTIP_STYLE = {
  contentStyle: {
    background: '#fff', border: '1px solid #e5e7eb',
    borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,.1)',
    fontSize: 12,
  },
  labelStyle:  { color: '#111827', fontWeight: 600 },
  itemStyle:   { color: '#374151' },
}

const MAX_LIVE = 40
const DAY_NAMES = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
const DAY_SHORT = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb']

const formatHour12 = (h) => `${h % 12 || 12} ${h >= 12 ? 'PM' : 'AM'}`

const formatCompact = (num) => {
  if (num === null || num === undefined) return '—';
  const absNum = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  if (absNum >= 1000000) return sign + (absNum / 1000000).toFixed(1).replace(/\.0$/, '').replace('.', ',') + 'M';
  if (absNum >= 1000) return sign + (absNum / 1000).toFixed(1).replace(/\.0$/, '').replace('.', ',') + 'k';
  return num.toString();
}

// ─── Custom Tooltip ───────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }) => {
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

// ─── KPI Card ─────────────────────────────────────────────────
function KpiCard({ title, value, colorClass, badge, badgeType }) {
  return (
    <div className={`kpi-card k-${colorClass}`}>
      <div className="kpi-body">
        <span className="kpi-label">{title}</span>
        <span className="kpi-value" title={value}>{value ?? '—'}</span>
        {badge && (
          <span className={`kpi-badge ${badgeType || 'neutral'}`}>{badge}</span>
        )}
      </div>
    </div>
  )
}

// ─── Aforo Card ───────────────────────────────────────────────
function AforoCard({ actual, limite, pct, alertActive }) {
  return (
    <div className={`kpi-card k-amber ${alertActive ? 'alert-pulse' : ''}`}>
      <div className="aforo-body">
        <span className="kpi-label">Aforo Actual</span>
        <div className="aforo-row">
          <span className="aforo-value">{actual}</span>
          <span className="aforo-limit">/ {limite}</span>
        </div>
        <div className="aforo-bar">
          <div
            className={`aforo-fill ${pct >= 90 ? 'danger' : ''}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
        <span className={`kpi-badge ${pct >= 80 ? 'warn' : 'up'}`}>
          {pct >= 80
            ? <><AlertTriangle size={11} /> {pct}% — Capacidad crítica</>
            : <>{pct}% de capacidad</>}
        </span>
      </div>
    </div>
  )
}

// ─── Camera row ───────────────────────────────────────────────
function CamRow({ cam, state }) {
  const { in: inC = 0, out: outC = 0, lastSeen } = state || {}
  const ocp   = Math.max(0, inC - outC)
  const isNew = lastSeen && Date.now() - lastSeen < 10000

  let statusLabel = 'Sin datos'
  let statusClass = 'offline'
  
  if (isNew && ocp > 30) { statusLabel = 'Alto Tráfico'; statusClass = 'high' }
  else if (isNew)         { statusLabel = 'Activo';       statusClass = 'active' }
  else if (state)         { statusLabel = 'Bajo Tráfico'; statusClass = 'low' }

  return (
    <tr>
      <td className="cam-name">{cam.name}</td>
      <td>{cam.ip}</td>
      <td>{inC > 0 ? inC.toLocaleString('es-PE') : '—'}</td>
      <td>{outC > 0 ? outC.toLocaleString('es-PE') : '—'}</td>
      <td>{ocp > 0 ? ocp.toLocaleString('es-PE') : '—'}</td>
      <td>
        <span className={`status-badge ${statusClass}`}>
          <span className="status-badge-dot" />
          {statusLabel}
        </span>
      </td>
      <td style={{ fontFamily: 'monospace', fontSize: '.7rem' }}>
        {lastSeen ? new Date(lastSeen).toLocaleTimeString('es-PE') : '—'}
      </td>
    </tr>
  )
}

// ═══════════════════════════════════════════════════════════════
export default function Dashboard() {
  const [aforoLimite, setAforoLimite] = useState(() => parseInt(localStorage.getItem('AFORO_LIMITE')) || 150)
  
  useEffect(() => {
    const handleStorage = () => setAforoLimite(parseInt(localStorage.getItem('AFORO_LIMITE')) || 150)
    window.addEventListener('storage', handleStorage)
    return () => window.removeEventListener('storage', handleStorage)
  }, [])

  // Estado de la cámara activa
  const [cameras,       setCameras]       = useState([])
  const [activeCamId,   setActiveCamId]   = useState(null)
  const [camStates,     setCamStates]     = useState({})      // { camId: { in, out, lastSeen } }
  const [livePoints,    setLivePoints]    = useState([])      // datos para el gráfico de línea
  const [todayHourly,   setTodayHourly]   = useState(() => new Array(24).fill(null).map(() => ({ in: 0, out: 0 })))
  const [weeklyData,    setWeeklyData]    = useState({})      // { 'YYYY-MM-DD': { in, out } }
  const [periodTab,     setPeriodTab]     = useState('live')

  // Para la cámara activa, calcular el aforo de toda su zona
  const activeCam = cameras.find(c => c.id === activeCamId)
  const activeState = camStates[activeCamId] || { in: 0, out: 0 }
  
  let aforo = 0
  let currentLimite = aforoLimite
  if (activeCam) {
    const zoneName = (activeCam.zone && activeCam.zone.trim() !== '') ? activeCam.zone : activeCam.name
    const camerasInZone = cameras.filter(c => {
      const cZone = (c.zone && c.zone.trim() !== '') ? c.zone : c.name
      return cZone === zoneName
    })
    
    const zoneIn = camerasInZone.reduce((sum, c) => sum + (camStates[c.id]?.in || 0), 0)
    const zoneOut = camerasInZone.reduce((sum, c) => sum + (camStates[c.id]?.out || 0), 0)
    aforo = Math.max(0, zoneIn - zoneOut)
    
    const maxCap = Math.max(...camerasInZone.map(c => c.max_capacity || 0))
    if (maxCap > 0) currentLimite = maxCap
  } else {
    aforo = Math.max(0, activeState.in - activeState.out)
  }
  
  const aforoPct = Math.round((aforo / currentLimite) * 100)

  // ─── Hora pico ───────────────────────────────────────────────
  const horaPico = (() => {
    const totals = todayHourly.map((h, i) => ({ h: i, t: h.in + h.out }))
    const peak   = totals.reduce((a, b) => b.t > a.t ? b : a, { h: 0, t: 0 })
    return peak.t > 0 ? { hora: formatHour12(peak.h), total: peak.t } : null
  })()

  // ─── Día más activo ──────────────────────────────────────────
  const topDay = (() => {
    const entries = Object.entries(weeklyData).sort((a,b) => (b[1].in+b[1].out) - (a[1].in+a[1].out))
    if (!entries.length) return null
    const [date, vals] = entries[0]
    const dt = new Date(date + 'T00:00:00')
    const dayName = DAY_NAMES[dt.getDay()]
    const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    const dateFormatted = `${dt.getDate()} ${months[dt.getMonth()]} ${dt.getFullYear()}`
    return { name: dayName, date: dateFormatted, count: vals.in + vals.out }
  })()

  // ─── Datos para barras por hora ──────────────────────────────
  const hourBarData = todayHourly.map((h, i) => ({
    hora: formatHour12(i),
    Entradas: h.in,
    Salidas:  h.out,
    total:    h.in + h.out,
  }))

  const maxHourTotal = Math.max(...hourBarData.map(d => d.total), 1)

  // ─── Datos para donut ────────────────────────────────────────
  const donutData = [
    { name: 'Entradas', value: activeState.in  },
    { name: 'Salidas',  value: activeState.out },
  ]

  // ─── Datos para semana ───────────────────────────────────────
  const weekBarData = Object.keys(weeklyData).sort().slice(-7).map(d => {
    const dt = new Date(d + 'T00:00:00')
    return {
      dia:      `${DAY_SHORT[dt.getDay()]} ${dt.getDate()}`,
      Entradas: weeklyData[d].in,
      Salidas:  weeklyData[d].out,
    }
  })

  // ─── WebSocket handler ───────────────────────────────────────
  const handleMessage = useCallback((data) => {
    const { camera_id, in_count, out_count, timestamp } = data
    const camId = parseInt(camera_id, 10)
    const ts    = new Date(timestamp)
    const h     = ts.getHours()
    const day   = timestamp.slice(0, 10)
    const now   = Date.now()

    setCamStates(prev => ({
      ...prev,
      [camId]: { in: in_count, out: out_count, lastSeen: now },
    }))

    // Acumular horas (solo hoy)
    const today = new Date().toISOString().slice(0, 10)
    if (timestamp.slice(0, 10) === today) {
      setTodayHourly(prev => {
        const next = [...prev]
        next[h] = { in: next[h].in + in_count, out: next[h].out + out_count }
        return next
      })
    }

    // Acumular semana
    setWeeklyData(prev => {
      const dayEntry = prev[day] || { in: 0, out: 0 }
      return { ...prev, [day]: { in: dayEntry.in + in_count, out: dayEntry.out + out_count } }
    })

    // Gráfico de línea en vivo (solo cámara activa)
    if (camId === activeCamId || activeCamId === null) {
      const label = ts.toLocaleTimeString('es-PE', { hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:true })
      setLivePoints(prev => {
        const next = [...prev, { t: label, Entradas: in_count, Salidas: out_count }]
        return next.length > MAX_LIVE ? next.slice(-MAX_LIVE) : next
      })
    }
  }, [activeCamId])

  const { connected } = useWebSocket(handleMessage)

  // ─── Carga de cámaras ────────────────────────────────────────
  useEffect(() => {
    api.getCameras().then(cams => {
      setCameras(cams)
      if (cams.length) setActiveCamId(cams[0].id)
    }).catch(() => {})
  }, [])

  // ─── Carga histórica inicial (últimos 7 días) ─────────────────
  useEffect(() => {
    api.getHistorical({ limit: 5000 }).then(json => {
      const today   = new Date().toISOString().slice(0, 10)
      const weekAgo = new Date(Date.now() - 7*86400000).toISOString().slice(0,10)
      const rows    = (json.data || []).filter(e => e.event_type !== 'hourly_heartbeat' && e.timestamp.slice(0,10) >= weekAgo)

      const newHourly = new Array(24).fill(null).map(() => ({ in: 0, out: 0 }))
      const newWeekly = {}

      rows.forEach(e => {
        const d = e.timestamp.slice(0, 10)
        const h = new Date(e.timestamp).getHours()
        if (d === today) {
          newHourly[h].in  += e.in_count  || 0
          newHourly[h].out += e.out_count || 0
        }
        if (!newWeekly[d]) newWeekly[d] = { in: 0, out: 0 }
        newWeekly[d].in  += e.in_count  || 0
        newWeekly[d].out += e.out_count || 0
      })

      setTodayHourly(newHourly)
      setWeeklyData(newWeekly)
    }).catch(() => {})
  }, [])

  const today = new Date().toISOString().slice(0, 10)
  const subtitle = activeCam
    ? `Cámara activa: ${activeCam.name} — ${activeCam.ip}`
    : 'Cargando cámaras…'

  return (
    <>
      <Topbar
        title="Monitoreo en Tiempo Real"
        subtitle={subtitle}
        connected={connected}
        exportParams={{ dateFrom: today, dateTo: today }}
      >
        <span className="live-badge">
          <span className="live-dot" />
          Live
        </span>
        <select
          className="select-field"
          value={activeCamId ?? ''}
          onChange={e => setActiveCamId(parseInt(e.target.value, 10))}
        >
          {cameras.map(c => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
        </select>
      </Topbar>

      <div className="page-body">



        {/* ─── KPIs ──────────────────────────────────────────── */}
        <div className="kpi-grid">
          <AforoCard
            actual={aforo}
            limite={currentLimite}
            pct={aforoPct}
            alertActive={aforoPct >= 80}
          />
          <KpiCard
            title="Entradas" value={activeState.in.toLocaleString('es-PE')}
            colorClass="green"
            badge={<><TrendingUp size={11} /> Tiempo real</>} badgeType="up"
          />
          <KpiCard
            title="Salidas" value={activeState.out.toLocaleString('es-PE')}
            colorClass="red"
            badge={<><Minus size={11} /> Tiempo real</>} badgeType="neutral"
          />
          <KpiCard
            title="Hora Pico (Hoy)" value={horaPico?.hora ?? '—'}
            colorClass="amber"
            badge={horaPico ? `${horaPico.total.toLocaleString('es-PE')} cruces` : 'sin datos'}
            badgeType="warn"
          />
          <KpiCard
            title="Día Más Activo"
            value={topDay ? topDay.name : '—'}
            icon={TrendingUp}
            colorClass="purple"
            badge={topDay ? `${topDay.date} / ${topDay.count} cruces` : ''}
          />
        </div>

        {/* ─── Alerta de aforo ─────────────────────────────── */}
        {aforoPct >= 80 && (
          <div className="alert-banner">
            <div className="alert-body">
              <div className="alert-icon">
                <AlertTriangle size={18} />
              </div>
              <div className="alert-text">
                <strong>Alerta de Aforo — {activeCam?.name}</strong>
                <span>
                  {aforo} personas dentro de {aforoLimite} permitidas ({aforoPct}% de capacidad).
                  Se recomienda tomar medidas de control de acceso.
                </span>
              </div>
            </div>
            <button type="button" className="btn btn-amber">Revisar</button>
          </div>
        )}

        {/* ─── Fila 1: Flujo en vivo + Donut ──────────────── */}
        <div className="charts-row cols-2-1">

          {/* Gráfico de flujo en tiempo real */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Flujo en Tiempo Real
              </span>
              <div className="period-tabs">
                {['live','1h'].map(p => (
                  <button type="button"
                    key={p}
                    className={`period-tab ${periodTab === p ? 'active' : ''}`}
                    onClick={() => setPeriodTab(p)}
                  >
                    {p === 'live' ? 'En Vivo' : '1 hora'}
                  </button>
                ))}
              </div>
            </div>
            <div className="card-body chart-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={livePoints} margin={{ top:5, right:15, left:-10, bottom:0 }}>
                  <defs>
                    <linearGradient id="gIn"  x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={"var(--teal)"} stopOpacity={.15}/>
                      <stop offset="95%" stopColor={"var(--teal)"} stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="gOut" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={"var(--amber)"} stopOpacity={.12}/>
                      <stop offset="95%" stopColor={"var(--amber)"} stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={"var(--grid)"} />
                  <XAxis dataKey="t" tick={{ fontSize:11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                  <YAxis tickFormatter={formatCompact} tick={{ fontSize:11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize:12 }} />
                  <Area type="monotone" dataKey="Entradas" stroke={"var(--teal)"} fill="url(#gIn)"  strokeWidth={2} dot={false} />
                  <Area type="monotone" dataKey="Salidas"  stroke={"var(--amber)"}   fill="url(#gOut)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Gráfico de donut */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Distribución
              </span>
            </div>
            <div className="card-body chart-wrap-sm" style={{ display:'flex', flexDirection:'column', alignItems:'center' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%" cy="50%"
                    innerRadius={55} outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    <Cell fill={"var(--teal)"} />
                    <Cell fill={"var(--amber)"}   />
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display:'flex', gap:'1.5rem', fontSize:12, fontWeight:600, marginTop:4 }}>
                <span style={{ color: "var(--teal)", display:'flex', alignItems:'center', gap:4 }}>
                  <span style={{ width:10, height:10, borderRadius:'50%', background: "var(--teal)", display:'inline-block' }}/>
                  Entradas
                </span>
                <span style={{ color: "var(--amber)", display:'flex', alignItems:'center', gap:4 }}>
                  <span style={{ width:10, height:10, borderRadius:'50%', background: "var(--amber)", display:'inline-block' }}/>
                  Salidas
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* ─── Fila 2: Barras por hora + Barras semana ─────── */}
        <div className="charts-row cols-1-1">

          {/* Entradas por Hora */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Entradas por Hora (Hoy)
              </span>
            </div>
            <div className="card-body chart-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={hourBarData} margin={{ top:5, right:10, left:-15, bottom:0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={"var(--grid)"} vertical={false} />
                  <XAxis dataKey="hora" tick={{ fontSize:10, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={formatCompact} tick={{ fontSize:11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize:12 }} />
                  <Bar dataKey="Entradas" fill={"var(--teal)"}  radius={[4,4,0,0]} />
                  <Bar dataKey="Salidas" fill={"var(--amber)"} radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Actividad últimos 7 días */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">
                Actividad — Últimos 7 Días
              </span>
            </div>
            <div className="card-body chart-wrap">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={weekBarData} margin={{ top:5, right:10, left:-15, bottom:0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={"var(--grid)"} vertical={false} />
                  <XAxis dataKey="dia" tick={{ fontSize:11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} />
                  <YAxis tickFormatter={formatCompact} tick={{ fontSize:11, fill: "var(--text-muted)" }} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize:12 }} />
                  <Bar dataKey="Entradas" fill={"var(--teal)"}  radius={[4,4,0,0]} />
                  <Bar dataKey="Salidas"  fill={"var(--amber)"} radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

        {/* ─── Tabla de cámaras ─────────────────────────────── */}
        <div className="card">
          <div className="card-header">
              <span className="card-title">
                Sensores de Cámara
              </span>
            <span style={{ fontSize:'.75rem', color:'var(--text-muted)' }}>
              {cameras.length} cámaras configuradas
            </span>
          </div>
          <div className="cam-table-wrap">
            <table className="cam-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Ubicación</th>
                  <th>Entradas</th>
                  <th>Salidas</th>
                  <th>Ocupación</th>
                  <th>Estado</th>
                  <th>Última Act.</th>
                </tr>
              </thead>
              <tbody>
                {cameras.length === 0 ? (
                  <tr><td colSpan={7} style={{ textAlign:'center', color:'var(--text-muted)', padding:'1.5rem' }}>
                    Conectando con el backend…
                  </td></tr>
                ) : (
                  cameras.map(cam => (
                    <CamRow key={cam.id} cam={cam} state={camStates[cam.id]} />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </>
  )
}
