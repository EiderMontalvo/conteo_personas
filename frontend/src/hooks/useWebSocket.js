// src/hooks/useWebSocket.js
import { useCallback, useEffect, useRef, useState } from 'react'

// Conectar directamente al backend FastAPI (el proxy WS de Vite a veces no es fiable en dev)
const WS_URL = 'ws://localhost:8000/ws/live'
const RETRY_MS = 3000

/**
 * Hook que mantiene una conexión WebSocket persistente con reconexión
 * automática. Devuelve el último mensaje recibido y el estado de conexión.
 */
export function useWebSocket(onMessage) {
  const [connected, setConnected] = useState(false)
  const onMsgRef  = useRef(onMessage)

  // Mantener la ref al callback actualizada sin reconectar
  useEffect(() => { onMsgRef.current = onMessage }, [onMessage])

  useEffect(() => {
    let ws = null
    let retryTimer = null

    const connect = () => {
      ws = new WebSocket(WS_URL)

      ws.onopen = () => {
        setConnected(true)
        if (retryTimer) { clearTimeout(retryTimer); retryTimer = null }
      }

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data)
          onMsgRef.current?.(data)
        } catch { /* ignorar mensajes mal formados */ }
      }

      ws.onclose = () => {
        setConnected(false)
        retryTimer = setTimeout(connect, RETRY_MS)
      }

      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      if (retryTimer) clearTimeout(retryTimer)
      if (ws) {
        ws.onclose = null
        ws.close()
      }
    }
  }, [])

  return { connected }
}
