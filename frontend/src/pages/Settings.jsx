import { useState, useEffect } from 'react'
import { Save, Settings as SettingsIcon, Camera, Server, Search, Plus, X, Wifi, AlertCircle, CheckCircle, Loader } from 'lucide-react'
import Topbar from '../components/Topbar'
import { useToast } from '../context/ToastContext'

const API = 'http://localhost:8000/api/v1'

// ─── Hook para datos ────────────────────────────────────────────────────────

function useCameras() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)

  const reload = () => {
    setLoading(true)
    fetch(`${API}/cameras`)
      .then(r => r.json())
      .then(res => setCameras(res.data || []))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(reload, [])
  return { cameras, setCameras, loading, reload }
}

// ─── Modal: Agregar/Editar Cámara ───────────────────────────────────────────

function CameraModal({ initial, onClose, onSaved }) {
  const { addToast } = useToast()
  const isNew = !initial?.id
  const [form, setForm] = useState({
    name: initial?.name || '',
    ip_address: initial?.ip_address || initial?.ip || '',
    role: initial?.role || 'both',
    zone: initial?.zone || '',
    max_capacity: initial?.max_capacity || 150,
    location: initial?.location || '',
    operating_hours_start: initial?.operating_hours_start || '00:00',
    operating_hours_end: initial?.operating_hours_end || '23:59',
  })
  const [saving, setSaving] = useState(false)

  const f = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const handleSave = async () => {
    if (!form.name.trim()) return addToast('El nombre es obligatorio', 'error')
    if (!form.ip_address.trim()) return addToast('La IP es obligatoria', 'error')
    setSaving(true)
    try {
      const url = isNew ? `${API}/cameras` : `${API}/cameras/${initial.id}`
      const method = isNew ? 'POST' : 'PUT'
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (data.ok) {
        addToast(isNew ? `✅ Cámara "${form.name}" agregada` : `✅ Cámara "${form.name}" actualizada`, 'success')
        onSaved()
        onClose()
      } else {
        addToast(data.detail || data.error || 'Error al guardar', 'error')
      }
    } catch {
      addToast('Error de conexión', 'error')
    }
    setSaving(false)
  }

  const roleLabels = { both: 'Entrada y Salida', in_only: 'Solo Entrada', out_only: 'Solo Salida' }

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <div className="modal-header">
          <span className="modal-title">
            <Camera size={18} className="text-amber" />
            {isNew ? 'Agregar Cámara' : `Editar: ${initial.name}`}
          </span>
          <button className="icon-btn" onClick={onClose}><X size={18} /></button>
        </div>
        <div className="modal-body">
          {isNew && (
            <div className="info-banner">
              <AlertCircle size={14} />
              <span>La cámara debe tener <strong>ONVIF habilitado</strong> en su interfaz web antes de continuar.</span>
            </div>
          )}

          <div className="form-grid">
            <label className="form-field span-2">
              <span className="form-label">Nombre descriptivo *</span>
              <input className="form-input" value={form.name} onChange={e => f('name', e.target.value)} placeholder="Ej. Puerta Principal" />
            </label>

            <label className="form-field">
              <span className="form-label">Dirección IP *</span>
              <input className="form-input font-mono" value={form.ip_address} onChange={e => f('ip_address', e.target.value)} placeholder="192.168.1.100" />
            </label>

            <label className="form-field">
              <span className="form-label">Aforo máximo (personas)</span>
              <input type="number" min="1" className="form-input" value={form.max_capacity} onChange={e => f('max_capacity', parseInt(e.target.value) || 150)} />
            </label>

            <label className="form-field">
              <span className="form-label">Dirección de conteo</span>
              <select className="form-input" value={form.role} onChange={e => f('role', e.target.value)}>
                {Object.entries(roleLabels).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>

            <label className="form-field">
              <span className="form-label">Grupo / Zona</span>
              <input className="form-input" value={form.zone} onChange={e => f('zone', e.target.value)} placeholder="Ej. planta_baja (opcional)" />
            </label>

            <label className="form-field">
              <span className="form-label">Inicio horario operativo</span>
              <input type="time" className="form-input" value={form.operating_hours_start} onChange={e => f('operating_hours_start', e.target.value)} />
            </label>

            <label className="form-field">
              <span className="form-label">Fin horario operativo</span>
              <input type="time" className="form-input" value={form.operating_hours_end} onChange={e => f('operating_hours_end', e.target.value)} />
            </label>

            <label className="form-field span-2">
              <span className="form-label">Descripción de ubicación</span>
              <input className="form-input" value={form.location} onChange={e => f('location', e.target.value)} placeholder="Ej. Pasillo Norte, Piso 2 (opcional)" />
            </label>
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-outline" onClick={onClose} disabled={saving}>Cancelar</button>
          <button className="btn btn-success" onClick={handleSave} disabled={saving}>
            {saving ? <Loader size={14} className="spin" /> : <Save size={14} />}
            {isNew ? 'Guardar y Conectar' : 'Guardar cambios'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Panel: Escaneo de Red ──────────────────────────────────────────────────

function NetworkScanner({ onAdd }) {
  const [scanning, setScanning] = useState(false)
  const [results, setResults] = useState(null)
  const [selectedCam, setSelectedCam] = useState(null)

  const scan = async () => {
    setScanning(true)
    setResults(null)
    try {
      const res = await fetch(`${API}/cameras/discover`)
      const data = await res.json()
      setResults(data.data || [])
    } catch {
      setResults([])
    }
    setScanning(false)
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title"><Wifi size={16} className="text-teal" /> Descubrir Cámaras en la Red</span>
      </div>
      <div className="card-body">
        <p className="help-text">
          Escanea automáticamente la red local para encontrar cámaras ONVIF
          conectadas al switch PoE o NVR.
        </p>
        <button className="btn btn-primary" onClick={scan} disabled={scanning}>
          {scanning
            ? <><Loader size={14} className="spin" /> Escaneando red...</>
            : <><Search size={14} /> Escanear Red</>}
        </button>

        {scanning && (
          <div className="scan-progress">
            <div className="scan-pulse" />
            <span>Buscando cámaras... esto puede tardar hasta 15 segundos</span>
          </div>
        )}

        {results !== null && (
          <div className="scan-results">
            {results.length === 0 ? (
              <div className="empty-state">
                <AlertCircle size={24} />
                <p>No se encontraron cámaras en la red.</p>
                <small>Verifica que las cámaras estén encendidas y tengan ONVIF habilitado.</small>
              </div>
            ) : (
              <>
                <p className="scan-found">{results.length} dispositivo(s) encontrado(s)</p>
                <div className="device-list">
                  {results.map(cam => (
                    <div key={cam.ip} className={`device-card ${cam.already_added ? 'device-added' : ''}`}>
                      <div className="device-info">
                        <div className="device-ip">{cam.ip}</div>
                        <div className="device-meta">
                          {cam.manufacturer} · {cam.model} · Puerto {cam.port}
                        </div>
                      </div>
                      {cam.already_added
                        ? <span className="badge-added"><CheckCircle size={12} /> Ya agregada</span>
                        : <button className="btn btn-sm btn-outline" onClick={() => setSelectedCam(cam)}>
                            <Plus size={12} /> Agregar
                          </button>
                      }
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {selectedCam && (
        <CameraModal
          initial={selectedCam}
          onClose={() => setSelectedCam(null)}
          onSaved={() => { setSelectedCam(null); onAdd() }}
        />
      )}
    </div>
  )
}

// ─── Panel: Cámara existente ─────────────────────────────────────────────────

function CameraCard({ cam, onUpdated, onDeactivated }) {
  const { addToast } = useToast()
  const [editing, setEditing] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const deactivate = async () => {
    try {
      const res = await fetch(`${API}/cameras/${cam.id}`, { method: 'DELETE' })
      const data = await res.json()
      if (data.ok) {
        addToast(`Cámara "${cam.name}" desactivada`, 'success')
        onDeactivated()
      }
    } catch {
      addToast('Error de conexión', 'error')
    }
    setConfirming(false)
  }

  const statusColor = {
    Normal: 'var(--teal)',
    Advertencia: '#f59e0b',
    Crítico: '#ef4444',
    Excedido: '#991b1b',
  }[cam.status] || 'var(--teal)'

  return (
    <>
      <div className="camera-card">
        <div className="camera-card-header">
          <div className="camera-card-title">
            <Camera size={16} className="text-amber" />
            <span>{cam.name}</span>
            <span className="camera-ip">({cam.ip_address})</span>
          </div>
          <div className="camera-card-actions">
            {cam.status && (
              <span className="status-dot" style={{ background: statusColor }} title={cam.status} />
            )}
            <button className="icon-btn text-blue" onClick={() => setEditing(true)} title="Editar">
              <SettingsIcon size={14} />
            </button>
            <button className="icon-btn text-red" onClick={() => setConfirming(true)} title="Desactivar">
              <X size={14} />
            </button>
          </div>
        </div>
        <div className="camera-card-body">
          <div className="cam-meta-row">
            <span className="cam-meta-label">Rol</span>
            <span className="cam-meta-value">{
              { both: 'Entrada y Salida', in_only: 'Solo Entrada', out_only: 'Solo Salida' }[cam.role] || cam.role
            }</span>
          </div>
          {cam.zone && (
            <div className="cam-meta-row">
              <span className="cam-meta-label">Grupo</span>
              <span className="cam-meta-value">{cam.zone}</span>
            </div>
          )}
          <div className="cam-meta-row">
            <span className="cam-meta-label">Aforo</span>
            <span className="cam-meta-value">{cam.max_capacity} personas</span>
          </div>
          {cam.people_inside !== undefined && cam.people_inside !== null && (
            <div className="cam-meta-row">
              <span className="cam-meta-label">En local ahora</span>
              <span className="cam-meta-value" style={{ color: statusColor, fontWeight: 700 }}>{cam.people_inside}</span>
            </div>
          )}
          <div className="cam-meta-row">
            <span className="cam-meta-label">Horario</span>
            <span className="cam-meta-value">{cam.operating_hours_start} – {cam.operating_hours_end}</span>
          </div>
        </div>
      </div>

      {editing && (
        <CameraModal initial={cam} onClose={() => setEditing(false)} onSaved={onUpdated} />
      )}

      {confirming && (
        <div className="modal-overlay">
          <div className="modal-box" style={{ maxWidth: 400 }}>
            <div className="modal-header">
              <span className="modal-title"><AlertCircle size={18} className="text-red" /> Desactivar cámara</span>
            </div>
            <div className="modal-body">
              <p>¿Desactivar <strong>{cam.name}</strong>? El polling se detendrá. Puedes volver a agregarla desde "Escanear Red".</p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-outline" onClick={() => setConfirming(false)}>Cancelar</button>
              <button className="btn btn-danger" onClick={deactivate}>Desactivar</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// ─── Ajustes del Sistema ─────────────────────────────────────────────────────

function SystemSettingsPanel() {
  const { addToast } = useToast()
  const [form, setForm] = useState({
    update_interval: 3,
    heartbeat_interval: 3600,
    timezone: 'America/Lima',
    warning_threshold: 80,
    critical_threshold: 100,
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch(`${API}/settings`)
      .then(r => r.json())
      .then(res => { if (res.data) setForm(res.data) })
      .catch(console.error)
  }, [])

  const f = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const save = async () => {
    setSaving(true)
    try {
      const res = await fetch(`${API}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (data.ok) addToast('Configuración guardada', 'success')
      else addToast('Error al guardar', 'error')
    } catch {
      addToast('Error de conexión', 'error')
    }
    setSaving(false)
  }

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title"><Server size={16} className="text-teal" /> Configuración del Sistema</span>
      </div>
      <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <label className="form-field">
          <span className="form-label">Zona Horaria</span>
          <input className="form-input" value={form.timezone} onChange={e => f('timezone', e.target.value)} placeholder="America/Lima" />
        </label>
        <div className="form-grid">
          <label className="form-field">
            <span className="form-label">Umbral Advertencia (%)</span>
            <input type="number" className="form-input" value={form.warning_threshold} onChange={e => f('warning_threshold', parseInt(e.target.value))} />
          </label>
          <label className="form-field">
            <span className="form-label">Umbral Crítico (%)</span>
            <input type="number" className="form-input" value={form.critical_threshold} onChange={e => f('critical_threshold', parseInt(e.target.value))} />
          </label>
          <label className="form-field">
            <span className="form-label">Intervalo de polling (seg)</span>
            <input type="number" min="2" className="form-input" value={form.update_interval} onChange={e => f('update_interval', parseInt(e.target.value))} />
          </label>
          <label className="form-field">
            <span className="form-label">Heartbeat inactividad (seg)</span>
            <input type="number" min="60" className="form-input" value={form.heartbeat_interval} onChange={e => f('heartbeat_interval', parseInt(e.target.value))} />
          </label>
        </div>
        <button className="btn btn-success" onClick={save} disabled={saving} style={{ alignSelf: 'flex-start' }}>
          {saving ? <Loader size={14} className="spin" /> : <Save size={14} />}
          Guardar Sistema
        </button>
      </div>
    </div>
  )
}

// ─── Página Principal ────────────────────────────────────────────────────────

export default function Settings() {
  const { cameras, loading, reload } = useCameras()

  return (
    <>
      <Topbar title="Ajustes del Sistema" subtitle="Configuración de cámaras y parámetros del sistema" connected={true} />
      <div className="page-body">

        {/* Sección superior: Sistema + Escaneo */}
        <div className="settings-top-grid">
          <SystemSettingsPanel />
          <NetworkScanner onAdd={reload} />
        </div>

        {/* Sección: Cámaras configuradas */}
        <div className="section-header">
          <h3 className="section-title">Cámaras Configuradas</h3>
          <span className="badge-count">{cameras.length} activa{cameras.length !== 1 ? 's' : ''}</span>
        </div>

        {loading ? (
          <div className="loading-state"><Loader className="spin" size={24} /> Cargando cámaras...</div>
        ) : cameras.length === 0 ? (
          <div className="empty-cameras">
            <Camera size={40} className="text-gray-300" />
            <p>No hay cámaras configuradas.</p>
            <small>Usa "Escanear Red" para descubrir cámaras conectadas al switch PoE.</small>
          </div>
        ) : (
          <div className="cameras-grid">
            {cameras.map(cam => (
              <CameraCard key={cam.id} cam={cam} onUpdated={reload} onDeactivated={reload} />
            ))}
          </div>
        )}
      </div>
    </>
  )
}
