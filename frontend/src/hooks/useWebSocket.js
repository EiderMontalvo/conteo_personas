import { useEffect, useRef, useState } from 'react'

// Directo al backend en el mismo host que sirve la página, para que funcione
// también desde otro equipo de la red (el proxy WS de Vite no es fiable en dev).
const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000/ws/live`
const RETRY_MS = 3000

/** Conexión WebSocket persistente con reconexión automática. */
export function useWebSocket(onMessage) {
  const [connected, setConnected] = useState(false)
  const onMsgRef = useRef(onMessage)

  useEffect(() => { onMsgRef.current = onMessage }, [onMessage])

  useEffect(() => {
    let ws = null
    let retryTimer = null

    const connect = () => {
      ws = new WebSocket(WS_URL)
      ws.onopen = () => setConnected(true)
      ws.onmessage = (e) => {
        try {
          onMsgRef.current?.(JSON.parse(e.data))
        } catch { /* mensaje mal formado */ }
      }
      ws.onclose = () => {
        setConnected(false)
        retryTimer = setTimeout(connect, RETRY_MS)
      }
      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      clearTimeout(retryTimer)
      if (ws) {
        ws.onclose = null
        ws.onmessage = null
        ws.onerror = null
        // Cerrar mientras conecta da "closed before the connection is established"
        // (pasa siempre con el doble montaje de StrictMode): se cierra al abrir.
        if (ws.readyState === WebSocket.CONNECTING) ws.onopen = () => ws.close()
        else ws.close()
      }
    }
  }, [])

  return { connected }
}
