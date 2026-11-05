import { CheckCircle, Warning, WarningCircle } from '@phosphor-icons/react'

// Colores usados desde JS (gráficos SVG). Deben coincidir con los tokens de index.css (tema oscuro).
export const SERIES = { in: '#2fc6d6', out: '#8590a2' }
export const STATUS_COLORS = { ok: '#3cc287', warn: '#e8a93c', danger: '#f26b5e' }
/** Categorías (franjas del día, cámaras): familia del acento; el gris queda para "Salidas". */
export const CATEGORY = ['#4a6d8c', '#8ee3ec', '#2fc6d6', '#1a8a96', '#8590a2', '#c3cad4']
export const CHART_AXIS = { fontSize: 12, fill: '#8a93a0' }
export const CHART_GRID = '#232a33'
export const TRACK = '#232932'
export const REF_LINE = '#e6e9ee'
export const CURSOR = 'rgba(255, 255, 255, 0.05)'
export const HEAT = (alpha) => `rgba(47, 198, 214, ${alpha})`
export const HEAT_EMPTY = 'rgba(255, 255, 255, 0.04)'

const CAPACITY_META = {
  Normal: { icon: CheckCircle, cls: 'text-ok', ring: STATUS_COLORS.ok },
  Advertencia: { icon: Warning, cls: 'text-warn', ring: STATUS_COLORS.warn },
  'Crítico': { icon: WarningCircle, cls: 'text-danger', ring: STATUS_COLORS.danger },
  Excedido: { icon: WarningCircle, cls: 'text-danger', ring: STATUS_COLORS.danger },
}
export const capacityMeta = (status) => CAPACITY_META[status] ?? CAPACITY_META.Normal
