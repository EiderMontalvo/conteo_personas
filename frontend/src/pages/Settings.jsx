import { useState, useEffect } from 'react'
import { Save, Settings as SettingsIcon, Camera, Server, Clock } from 'lucide-react'
import Topbar from '../components/Topbar'
import { api } from '../hooks/useApi'
import { useToast } from '../context/ToastContext'

export default function Settings() {
  const { addToast } = useToast()
  const [cameras, setCameras] = useState([])
  const [systemSettings, setSystemSettings] = useState({
    update_interval: 1000,
    heartbeat_interval: 3600,
    timezone: 'America/Lima',
    warning_threshold: 80,
    critical_threshold: 95
  })
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // Fetch system settings
    fetch('http://localhost:8000/api/settings')
      .then(res => res.json())
      .then(data => {
        if (data && data.update_interval) setSystemSettings(data)
      })
      .catch(console.error)

    // Fetch extended cameras config
    fetch('http://localhost:8000/api/cameras/config')
      .then(res => res.json())
      .then(data => setCameras(data || []))
      .catch(console.error)
  }, [])

  const handleSystemSave = async () => {
    setLoading(true)
    try {
      const res = await fetch('http://localhost:8000/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(systemSettings)
      })
      if (res.ok) addToast('Configuración del sistema guardada', 'success')
      else addToast('Error al guardar configuración', 'error')
    } catch (e) {
      addToast('Error de conexión', 'error')
    }
    setLoading(false)
  }

  const handleCameraSave = async (camId) => {
    setLoading(true)
    const cam = cameras.find(c => c.id === camId)
    try {
      const res = await fetch(`http://localhost:8000/api/cameras/${camId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: cam.name,
          zone: cam.zone,
          max_capacity: cam.max_capacity,
          count_direction: cam.count_direction,
          virtual_line: cam.virtual_line,
          operating_hours_start: cam.operating_hours_start,
          operating_hours_end: cam.operating_hours_end,
          is_active: cam.is_active
        })
      })
      if (res.ok) addToast(`Cámara ${cam.name} actualizada`, 'success')
      else addToast('Error al guardar cámara', 'error')
    } catch (e) {
      addToast('Error de conexión', 'error')
    }
    setLoading(false)
  }

  const updateCameraField = (id, field, value) => {
    setCameras(prev => prev.map(c => c.id === id ? { ...c, [field]: value } : c))
  }

  return (
    <>
      <Topbar title="Ajustes del Sistema" subtitle="Configuración general y por cámara" connected={true} />
      <div className="page-body">
        
        <div className="flex gap-8 items-start lg:flex-row flex-col">
          
          {/* Ajustes Generales */}
          <div className="card lg:w-1/3 w-full">
            <div className="card-header">
              <span className="card-title"><Server size={16} className="text-teal" /> Sistema</span>
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <label className="flex flex-col gap-1.5">
                <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Intervalo de Actualización WS (ms)</span>
                <input type="number" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={systemSettings.update_interval} onChange={e => setSystemSettings({...systemSettings, update_interval: parseInt(e.target.value)})} />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Heartbeat Inactividad (segundos)</span>
                <input type="number" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={systemSettings.heartbeat_interval} onChange={e => setSystemSettings({...systemSettings, heartbeat_interval: parseInt(e.target.value)})} />
              </label>
              <label className="flex flex-col gap-1.5">
                <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Zona Horaria</span>
                <input type="text" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={systemSettings.timezone} onChange={e => setSystemSettings({...systemSettings, timezone: e.target.value})} />
              </label>
              <div className="grid grid-cols-2 gap-4">
                <label className="flex flex-col gap-1.5">
                  <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Umbral Advertencia (%)</span>
                  <input type="number" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={systemSettings.warning_threshold} onChange={e => setSystemSettings({...systemSettings, warning_threshold: parseInt(e.target.value)})} />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Umbral Crítico (%)</span>
                  <input type="number" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={systemSettings.critical_threshold} onChange={e => setSystemSettings({...systemSettings, critical_threshold: parseInt(e.target.value)})} />
                </label>
              </div>
              <label className="flex flex-col gap-1.5">
                <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Aforo Máximo Global (Defecto)</span>
                <input type="number" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" 
                  defaultValue={localStorage.getItem('AFORO_LIMITE') || 150} 
                  onBlur={e => {
                    localStorage.setItem('AFORO_LIMITE', e.target.value)
                    window.dispatchEvent(new Event('storage'))
                    addToast('Aforo global guardado localmente', 'success')
                  }} 
                />
              </label>
              <button type="button" className="btn btn-success" style={{ marginTop: '1rem', justifyContent: 'center' }} onClick={handleSystemSave} disabled={loading}>
                <Save size={16} /> Guardar Sistema
              </button>
            </div>
          </div>

          {/* Ajustes por Cámara */}
          <div className="flex flex-col gap-6 lg:w-2/3 w-full">
            <h3 className="m-0 text-xl font-bold text-gray-900">Ajustes por Cámara</h3>
            {cameras.map(cam => (
              <div key={cam.id} className="card">
                <div className="card-header" style={{ background: 'var(--surface-2)' }}>
                  <span className="card-title"><Camera size={16} className="text-amber" /> {cam.name} (IP: {cam.ip_address || 'N/A'})</span>
                </div>
                <div className="card-body" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Nombre</span>
                    <input type="text" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={cam.name || ''} onChange={e => updateCameraField(cam.id, 'name', e.target.value)} />
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Zona / Grupo</span>
                    <input type="text" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={cam.zone || ''} onChange={e => updateCameraField(cam.id, 'zone', e.target.value)} />
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Límite de Aforo (Personas)</span>
                    <input type="number" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={cam.max_capacity || 0} onChange={e => updateCameraField(cam.id, 'max_capacity', parseInt(e.target.value))} />
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Dirección Conteo</span>
                    <select className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={cam.count_direction || 'in_out'} onChange={e => updateCameraField(cam.id, 'count_direction', e.target.value)}>
                      <option value="in_out">Entrada y Salida</option>
                      <option value="in_only">Solo Entrada</option>
                      <option value="out_only">Solo Salida</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Inicio Horario (HH:MM)</span>
                    <input type="time" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={cam.operating_hours_start || ''} onChange={e => updateCameraField(cam.id, 'operating_hours_start', e.target.value)} />
                  </label>
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[0.75rem] font-semibold text-gray-500 uppercase tracking-wide">Fin Horario (HH:MM)</span>
                    <input type="time" className="bg-body border border-gray-200 rounded-sm px-3 py-1.5 text-[0.85rem] outline-none focus:border-amber transition-colors" value={cam.operating_hours_end || ''} onChange={e => updateCameraField(cam.id, 'operating_hours_end', e.target.value)} />
                  </label>
                  <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end', marginTop: '0.5rem' }}>
                    <button type="button" className="btn btn-outline" onClick={() => handleCameraSave(cam.id)} disabled={loading}>
                      <Save size={14} /> Guardar {cam.name}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>

        </div>
      </div>
    </>
  )
}
