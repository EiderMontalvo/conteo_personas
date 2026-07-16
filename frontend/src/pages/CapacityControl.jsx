import { useState, useEffect, useCallback } from 'react'
import { api } from '../hooks/useApi'
import { useWebSocket } from '../hooks/useWebSocket'
import Topbar from '../components/Topbar'
import { Users, AlertTriangle, ShieldCheck } from 'lucide-react'

export default function CapacityControl() {
  const [cameras, setCameras] = useState([])
  const [camStates, setCamStates] = useState({})
  const [settings, setSettings] = useState(null)
  
  useEffect(() => {
    api.getCameras().then(cams => setCameras(cams)).catch(console.error)
    // Simulated settings fetch (until implemented fully in API hook)
    fetch('http://localhost:8000/api/settings')
      .then(res => res.json())
      .then(data => setSettings(data))
      .catch(console.error)
  }, [])

  const handleMessage = useCallback((data) => {
    const { camera_id, in_count, out_count } = data
    setCamStates(prev => {
      const current = prev[camera_id] || { in: 0, out: 0 }
      return {
        ...prev,
        [camera_id]: { in: current.in + in_count, out: current.out + out_count }
      }
    })
  }, [])

  const { connected } = useWebSocket(handleMessage)

  const warningThreshold = settings?.warning_threshold || 80
  const criticalThreshold = settings?.critical_threshold || 95

  return (
    <>
      <Topbar title="Control de Aforo" subtitle="Monitoreo de ocupación por cámara" connected={connected} />
      <div className="page-body">

        
        <div className="kpi-grid">
          {(() => {
            const zonesMap = {}
            cameras.forEach(cam => {
              const zoneName = (cam.zone && cam.zone.trim() !== '') ? cam.zone : cam.name
              if (!zonesMap[zoneName]) {
                zonesMap[zoneName] = {
                  id: zoneName,
                  name: zoneName,
                  cameras: [],
                  max_capacity: cam.max_capacity || 100,
                  isGroup: !!(cam.zone && cam.zone.trim() !== '')
                }
              } else {
                zonesMap[zoneName].max_capacity = Math.max(zonesMap[zoneName].max_capacity, cam.max_capacity || 100)
              }
              zonesMap[zoneName].cameras.push(cam)
            })

            const zones = Object.values(zonesMap)

            if (zones.length === 0) {
              return (
                <div className="card text-center text-gray-500" style={{ padding: '3rem', gridColumn: '1 / -1' }}>
                  No hay cámaras configuradas en la base de datos.
                </div>
              )
            }

            return zones.map(zone => {
              const inCount = zone.cameras.reduce((sum, c) => sum + (camStates[c.id]?.in || 0), 0)
              const outCount = zone.cameras.reduce((sum, c) => sum + (camStates[c.id]?.out || 0), 0)
              const aforoActual = Math.max(0, inCount - outCount)
              const limite = zone.max_capacity
              const available = Math.max(0, limite - aforoActual)
              const pct = Math.round((aforoActual / limite) * 100)
              
              let status = 'normal'
              if (pct >= criticalThreshold) status = 'critical'
              else if (pct >= warningThreshold) status = 'warning'

              const colorClass = status === 'critical' ? 'red' : status === 'warning' ? 'amber' : 'green'
              const badgeType = status === 'critical' ? 'down' : status === 'warning' ? 'warn' : 'up'
              const statusText = status === 'critical' ? 'Crítico' : status === 'warning' ? 'Advertencia' : 'Normal'
              
              return (
                <div key={zone.id} className={`kpi-card k-${colorClass} ${status !== 'normal' ? 'alert-pulse' : ''}`}>
                  <div className={`kpi-icon-wrap i-${colorClass}`}>
                    <Users size={20} />
                  </div>
                  <div className="aforo-body">
                    <span className="kpi-label">{zone.name}</span>
                    <div className="aforo-row">
                      <span className="aforo-value">{aforoActual}</span>
                      <span className="aforo-limit">/ {limite}</span>
                    </div>
                    <div className="aforo-bar">
                      <div
                        className={`aforo-fill ${status === 'critical' ? 'danger' : ''}`}
                        style={{ width: `${Math.min(pct, 100)}%`, background: status === 'normal' ? 'var(--green)' : '' }}
                      />
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.3rem' }}>
                      <span className={`kpi-badge ${badgeType}`}>
                        {status !== 'normal' ? <><AlertTriangle size={11} /> {pct}% — {statusText}</> : <>{pct}% de ocupación</>}
                      </span>
                      {available > 0 && <span className="text-[0.65rem] font-semibold text-gray-500">{available} libres</span>}
                    </div>
                  </div>
                </div>
              )
            })
          })()}
        </div>
      </div>
    </>
  )
}
