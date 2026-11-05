import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from '../hooks/useApi'
import { useWebSocket } from '../hooks/useWebSocket'
import { localDayKey } from '../utils/format'

const LiveCtx = createContext(null)
const MAX_EVENTS = 40
const emptyHours = () => Array.from({ length: 24 }, () => ({ in: 0, out: 0 }))

/**
 * Estado en vivo compartido por todas las pantallas: una sola conexión WebSocket.
 * `states` y `status` se indexan por camera_id lógico (lo que envía el backend), no por la PK.
 */
export function LiveProvider({ children }) {
  const [cameras, setCameras] = useState([])
  const [loaded, setLoaded] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [states, setStates] = useState({})
  const [status, setStatus] = useState({})
  const [today, setToday] = useState(() => ({ day: localDayKey(), hours: emptyHours(), occupancy: {} }))
  const [events, setEvents] = useState([])
  const [lastMessageAt, setLastMessageAt] = useState(null)

  const refreshCameras = useCallback(() => {
    return api.getCameras()
      .then((res) => {
        const cams = res?.data ?? []
        setCameras(cams)
        setStates(Object.fromEntries(cams.map((c) => [c.camera_id, {
          people_inside: c.people_inside ?? 0,
          total_in: c.total_in ?? 0,
          total_out: c.total_out ?? 0,
        }])))
        setStatus(Object.fromEntries(cams.filter((c) => c.connection).map((c) => [c.camera_id, c.connection])))
        setLoadError(null)
      })
      .catch((e) => setLoadError(e))
      .finally(() => setLoaded(true))
  }, [])

  const loadToday = useCallback(() => {
    const today = localDayKey()
    return api.getHistorical({ dateFrom: today, limit: 10000 })
      .then((json) => {
        const next = emptyHours()
        const occupancy = {}
        const rows = (json?.data ?? []).slice().sort((a, b) => a.timestamp.localeCompare(b.timestamp))
        for (const e of rows) {
          if (e.event_type === 'hourly_heartbeat') continue
          const at = new Date(e.timestamp)
          next[at.getHours()].in += e.in_count || 0
          next[at.getHours()].out += e.out_count || 0
          ;(occupancy[e.camera_id] ??= []).push({ t: at.getTime(), v: e.people_inside ?? 0 })
        }
        setToday({ day: today, hours: next, occupancy })
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    refreshCameras()
    loadToday()
  }, [refreshCameras, loadToday])

  const handleMessage = useCallback((msg) => {
    if (!msg?.payload) return
    const p = msg.payload

    if (msg.type === 'camera_status') {
      setStatus((prev) => ({ ...prev, [p.camera_id]: p }))
      return
    }
    if (msg.type !== 'count_update') return

    const camId = Number(p.camera_id)
    const at = new Date(p.timestamp)
    setLastMessageAt(Date.now())

    // El backend ya envía los totales del día: se usan tal cual para no derivar.
    setStates((prev) => {
      const curr = prev[camId] ?? { people_inside: 0, total_in: 0, total_out: 0 }
      return {
        ...prev,
        [camId]: {
          people_inside: p.people_inside ?? Math.max(0, curr.people_inside + p.in_count - p.out_count),
          total_in: p.accum_in ?? curr.total_in + p.in_count,
          total_out: p.accum_out ?? curr.total_out + p.out_count,
          lastSeen: Date.now(),
        },
      }
    })

    const day = localDayKey(at)
    setToday((prev) => {
      const same = day === prev.day
      const hours = same ? prev.hours.map((h) => ({ ...h })) : emptyHours()
      hours[at.getHours()].in += p.in_count || 0
      hours[at.getHours()].out += p.out_count || 0
      const occupancy = same ? { ...prev.occupancy } : {}
      if (p.people_inside != null) {
        occupancy[camId] = [...(occupancy[camId] ?? []), { t: at.getTime(), v: p.people_inside }]
      }
      return { day, hours, occupancy }
    })

    setEvents((prev) => [{
      id: `${camId}-${p.timestamp}-${prev.length}`,
      camera_id: camId,
      camera_name: p.camera_name,
      timestamp: p.timestamp,
      in_count: p.in_count,
      out_count: p.out_count,
    }, ...prev].slice(0, MAX_EVENTS))
  }, [])

  const { connected } = useWebSocket(handleMessage)

  const value = useMemo(() => ({
    cameras, loaded, loadError, states, status, events,
    hourly: today.hours, hourlyDay: today.day, occupancy: today.occupancy,
    wsConnected: connected, lastMessageAt, refreshCameras,
  }), [cameras, loaded, loadError, states, status, today, events, connected, lastMessageAt, refreshCameras])

  return <LiveCtx.Provider value={value}>{children}</LiveCtx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useLive = () => useContext(LiveCtx)
