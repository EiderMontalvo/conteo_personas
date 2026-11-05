import { CheckCircle, ArrowsClockwise, WifiSlash, Pause } from '@phosphor-icons/react'

/** Cómo mostrar el estado de conexión de una cámara que reporta el backend. */
export function connectionMeta(conn) {
  if (!conn) return { label: 'Sin datos', tone: 'text-fg-3', icon: WifiSlash, ok: false }
  if (conn.state === 'connected') {
    return { label: conn.demo ? 'Conectada (demo)' : 'Conectada', tone: 'text-ok', icon: CheckCircle, ok: true }
  }
  if (conn.state === 'connecting') return { label: 'Conectando…', tone: 'text-fg-2', icon: ArrowsClockwise, ok: false }
  if (conn.state === 'reconnecting') return { label: 'Sin conexión', tone: 'text-danger', icon: WifiSlash, ok: false }
  return { label: 'Detenida', tone: 'text-fg-3', icon: Pause, ok: false }
}
