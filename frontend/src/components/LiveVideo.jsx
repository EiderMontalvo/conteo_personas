import { useEffect, useRef, useState } from 'react'
import { ArrowsClockwise, ArrowsOut, ArrowsIn, SignIn, SignOut, VideoCameraSlash } from '@phosphor-icons/react'
import { formatNumber } from '../utils/format'

const RETRY_MS = 15000

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <span className="num">
      {now.toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric' })}{' '}
      {now.toLocaleTimeString('es-PE', { hourCycle: 'h23' })}
    </span>
  )
}

const IVA_REFRESH_MS = 60000

/** Líneas virtuales IVA de la cámara; se refrescan para reflejar cambios hechos en la cámara. */
function useIvaLines(cameraId) {
  const [iva, setIva] = useState(null)
  useEffect(() => {
    if (cameraId == null) return
    let cancelled = false
    const load = () =>
      fetch(`/api/v1/cameras/${cameraId}/iva-lines`, { cache: 'no-store' })
        .then((r) => (r.ok ? r.json() : null))
        .then((body) => !cancelled && setIva(body?.data ?? null))
        .catch(() => !cancelled && setIva(null))
    load()
    const t = setInterval(load, IVA_REFRESH_MS)
    return () => {
      cancelled = true
      clearInterval(t)
    }
  }, [cameraId])
  return iva
}

/** Dibuja las líneas IVA en el mismo encuadre que el <img> (object-contain). */
function IvaOverlay({ iva }) {
  if (!iva?.lines?.length) return null
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox={`0 0 ${iva.width} ${iva.height}`}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
    >
      {iva.lines.map(({ line, points }) => {
        const [x1, y1] = points[0]
        const [x2, y2] = points[points.length - 1]
        const path = points.map(([x, y]) => `${x},${y}`).join(' ')
        return (
          <g key={line}>
            <polyline points={path} fill="none" stroke="#000" strokeOpacity="0.55" strokeWidth="7" vectorEffect="non-scaling-stroke" />
            <polyline points={path} fill="none" stroke="#ffd60a" strokeWidth="3" vectorEffect="non-scaling-stroke" />
            {[[x1, y1], [x2, y2]].map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r={iva.width / 160} fill="#ffd60a" stroke="#000" strokeOpacity="0.55" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            ))}
          </g>
        )
      })}
    </svg>
  )
}

/** Video MJPEG en vivo de una cámara a través del backend, con superposición de datos. */
export default function LiveVideo({ camera, connection, totals }) {
  const boxRef = useRef(null)
  const [attempt, setAttempt] = useState(0)
  const [phase, setPhase] = useState('loading') // loading | live | error
  const [reason, setReason] = useState(null)
  const [fullscreen, setFullscreen] = useState(false)
  const iva = useIvaLines(camera?.id)

  useEffect(() => {
    setPhase('loading')
    setReason(null)
  }, [camera?.id, attempt])

  useEffect(() => {
    if (phase !== 'error') return
    const t = setTimeout(() => setAttempt((a) => a + 1), RETRY_MS)
    return () => clearTimeout(t)
  }, [phase])

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === boxRef.current)
    document.addEventListener('fullscreenchange', onChange)
    return () => document.removeEventListener('fullscreenchange', onChange)
  }, [])

  // El <img> no expone el motivo del fallo: se consulta el snapshot para leer el detalle.
  const onError = () => {
    setPhase('error')
    fetch(`/api/v1/cameras/${camera.id}/snapshot`, { cache: 'no-store' })
      .then(async (r) => {
        if (r.ok) return setReason('El video se cortó. Reintentando…')
        const body = await r.json().catch(() => null)
        setReason(body?.detail ?? `Error ${r.status}`)
      })
      .catch(() => setReason('No hay conexión con el servidor.'))
  }

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen()
    else boxRef.current?.requestFullscreen?.()
  }

  if (!camera) return null
  const live = phase === 'live'

  return (
    <div ref={boxRef} className={`relative overflow-hidden bg-[#0d0e10] ${fullscreen ? 'h-full w-full' : 'aspect-video rounded-md'}`}>
      {phase !== 'error' && (
        <img
          key={`${camera.id}-${attempt}`}
          src={`/api/v1/cameras/${camera.id}/stream?k=${attempt}`}
          alt={`Video en vivo de ${camera.name}`}
          className={`h-full w-full object-contain transition-opacity duration-200 ${live ? 'opacity-100' : 'opacity-0'}`}
          onLoad={() => setPhase('live')}
          onError={onError}
        />
      )}

      {live && <IvaOverlay iva={iva} />}

      {!live && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center text-[#c9cbd1]">
          {phase === 'loading' ? (
            <>
              <ArrowsClockwise size={28} className="animate-spin text-[#8a8d96]" aria-hidden="true" />
              <p className="text-sm">Conectando con {camera.name}…</p>
            </>
          ) : (
            <>
              <VideoCameraSlash size={32} className="text-[#8a8d96]" aria-hidden="true" />
              <div>
                <p className="font-semibold text-white">Sin imagen de {camera.name}</p>
                <p className="mt-1 max-w-sm text-sm">{reason ?? 'Comprobando…'}</p>
              </div>
              <button type="button" className="btn h-8 border border-white/20 text-[13px] text-white hover:bg-white/10" onClick={() => setAttempt((a) => a + 1)}>
                <ArrowsClockwise size={16} aria-hidden="true" /> Reintentar ahora
              </button>
            </>
          )}
        </div>
      )}

      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 bg-gradient-to-b from-black/60 to-transparent p-3 text-[13px] text-white">
        <div className="min-w-0">
          <p className="truncate font-semibold">{camera.name}</p>
          <p className="num text-white/70">{camera.ip_address}</p>
        </div>
        <div className="flex items-center gap-2">
          {live && (
            <span className="inline-flex items-center gap-1.5 rounded-[3px] bg-black/50 px-2 py-1 text-xs font-bold">
              <span className="h-2 w-2 rounded-[1px] bg-[#ff4d3a]" aria-hidden="true" />
              EN VIVO
            </span>
          )}
          {connection?.state === 'reconnecting' && (
            <span className="rounded-[3px] bg-black/50 px-2 py-1 text-xs font-bold text-[#ffb4a8]">Conteo sin conexión</span>
          )}
          <button
            type="button"
            onClick={toggleFullscreen}
            className="pointer-events-auto inline-flex h-8 w-8 items-center justify-center rounded-[4px] bg-black/50 text-white hover:bg-black/70"
            aria-label={fullscreen ? 'Salir de pantalla completa' : 'Pantalla completa'}
          >
            {fullscreen ? <ArrowsIn size={18} /> : <ArrowsOut size={18} />}
          </button>
        </div>
      </div>

      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-gradient-to-t from-black/60 to-transparent p-3 text-[13px] text-white">
        <Clock />
        {totals && (
          <span className="inline-flex items-center gap-3 font-semibold">
            <span className="inline-flex items-center gap-1"><SignIn size={16} aria-hidden="true" /><span className="num">{formatNumber(totals.in)}</span><span className="sr-only">entradas</span></span>
            <span className="inline-flex items-center gap-1"><SignOut size={16} aria-hidden="true" /><span className="num">{formatNumber(totals.out)}</span><span className="sr-only">salidas</span></span>
          </span>
        )}
      </div>
    </div>
  )
}
