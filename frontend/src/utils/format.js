export const DAY_NAMES = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']
export const DAY_SHORT = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb']
export const MONTH_NAMES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
export const MONTH_SHORT = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

const pad = (n) => String(n).padStart(2, '0')

/** 'YYYY-MM-DD' del día local; toISOString() daría el día UTC (en Lima cambia a las 19:00). */
export const localDayKey = (date = new Date()) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`

export const daysAgoKey = (days) => {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return localDayKey(d)
}

export const parseDayKey = (key) => new Date(`${key}T00:00:00`)

export const formatHour12 = (h) => `${h % 12 || 12} ${h >= 12 ? 'p. m.' : 'a. m.'}`
export const formatHourShort = (h) => `${pad(h)}h`

export const formatNumber = (n) => (n ?? 0).toLocaleString('es-PE')

export const formatCompact = (num) => {
  if (num === null || num === undefined) return '—'
  const abs = Math.abs(num)
  const sign = num < 0 ? '-' : ''
  if (abs >= 1_000_000) return sign + (abs / 1_000_000).toFixed(1).replace(/\.0$/, '').replace('.', ',') + ' M'
  if (abs >= 10_000) return sign + (abs / 1_000).toFixed(1).replace(/\.0$/, '').replace('.', ',') + ' k'
  return num.toLocaleString('es-PE')
}

/** "Miércoles 4 de noviembre" */
export const formatLongDate = (date = new Date()) =>
  `${DAY_NAMES[date.getDay()]} ${date.getDate()} de ${MONTH_NAMES[date.getMonth()]}`

/** "Mié 4 Nov" a partir de 'YYYY-MM-DD' */
export const formatDayKey = (key) => {
  if (!key) return '—'
  const d = parseDayKey(key)
  return `${DAY_SHORT[d.getDay()]} ${d.getDate()} ${MONTH_SHORT[d.getMonth()]}`
}

export const formatTime = (iso, withSeconds = false) =>
  new Date(iso).toLocaleTimeString('es-PE', {
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23', ...(withSeconds && { second: '2-digit' }),
  })

export const formatDateTime = (iso) => {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-PE', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

/** "hace 12 s", "hace 3 min", "hace 2 h" */
export const formatAgo = (ms) => {
  if (ms == null) return null
  const s = Math.max(0, Math.round(ms / 1000))
  if (s < 60) return `hace ${s} s`
  const m = Math.round(s / 60)
  if (m < 60) return `hace ${m} min`
  return `hace ${Math.round(m / 60)} h`
}

export const roleLabel = (role) => ({
  both: 'Entrada y salida',
  in_only: 'Solo entrada',
  out_only: 'Solo salida',
  space: 'Espacio de aforo',
}[role] ?? role)
