import { useEffect, useState } from 'react'
import {
  ArrowsClockwise, CheckCircle, FloppyDisk, Info, MagnifyingGlass, PencilSimple, Plus, Power, VideoCamera, WarningCircle,
} from '@phosphor-icons/react'
import { api } from '../hooks/useApi'
import { useLive } from '../context/LiveContext'
import { useToast } from '../context/ToastContext'
import { formatNumber, roleLabel } from '../utils/format'
import { Card, CardHeader, EmptyState, Modal, PageHeader, StatusText } from '../components/ui'
import { connectionMeta } from '../components/connection'

const ROLE_OPTIONS = [
  { value: 'both', label: 'Entrada y salida', hint: 'Una línea que cuenta en ambos sentidos.' },
  { value: 'in_only', label: 'Solo entrada', hint: 'Ignora las salidas; útil con otra cámara para la salida.' },
  { value: 'out_only', label: 'Solo salida', hint: 'Ignora las entradas.' },
  { value: 'space', label: 'Espacio de aforo', hint: 'Aparece en la pantalla Aforo con su límite de personas.' },
]
const IP_RE = /^(25[0-5]|2[0-4]\d|1?\d?\d)(\.(25[0-5]|2[0-4]\d|1?\d?\d)){3}$/
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/

function Field({ label, error, hint, children, className = '' }) {
  return (
    <label className={`block ${className}`}>
      <span className="field-label">{label}</span>
      {children}
      {error
        ? <span className="mt-1 flex items-center gap-1 text-[13px] text-danger"><WarningCircle size={14} weight="bold" aria-hidden="true" />{error}</span>
        : hint && <span className="mt-1 block text-[13px] text-fg-2">{hint}</span>}
    </label>
  )
}

function CameraModal({ initial, onClose, onSaved }) {
  const { addToast } = useToast()
  const isNew = !initial?.id
  const [form, setForm] = useState({
    name: initial?.name ?? '',
    ip_address: initial?.ip_address ?? initial?.ip ?? '',
    role: initial?.role ?? 'both',
    zone: initial?.zone ?? '',
    max_capacity: initial?.max_capacity ?? 150,
    location: initial?.location ?? '',
    operating_hours_start: initial?.operating_hours_start ?? '00:00',
    operating_hours_end: initial?.operating_hours_end ?? '23:59',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }))

  const validate = () => {
    const e = {}
    if (!form.name.trim()) e.name = 'Escribe un nombre para reconocerla.'
    if (!IP_RE.test(form.ip_address.trim())) e.ip_address = 'IP no válida. Ejemplo: 192.168.1.100'
    if (!(Number(form.max_capacity) >= 1)) e.max_capacity = 'Debe ser al menos 1.'
    if (!TIME_RE.test(form.operating_hours_start)) e.operating_hours_start = 'Formato HH:MM'
    if (!TIME_RE.test(form.operating_hours_end)) e.operating_hours_end = 'Formato HH:MM'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  const save = async (ev) => {
    ev.preventDefault()
    if (saving || !validate()) return
    setSaving(true)
    const payload = {
      ...form,
      name: form.name.trim(),
      ip_address: form.ip_address.trim(),
      zone: form.zone.trim() || null,
      location: form.location.trim() || null,
      max_capacity: Number(form.max_capacity),
    }
    try {
      const json = isNew ? await api.createCamera(payload) : await api.updateCamera(initial.id, payload)
      if (!json.ok) throw new Error(json.error || 'respuesta inesperada')
      addToast(isNew ? `“${payload.name}” agregada. Conectando…` : `“${payload.name}” actualizada`, 'success')
      onSaved()
      onClose()
    } catch (e) {
      const msg = e.message.includes('409') ? 'Ya hay una cámara activa con esa IP.' : e.message
      addToast(`No se pudo guardar: ${msg}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  const role = ROLE_OPTIONS.find((r) => r.value === form.role)

  return (
    <Modal
      title={isNew ? 'Agregar cámara' : `Editar ${initial.name}`}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="btn-secondary" onClick={onClose} disabled={saving}>Cancelar</button>
          <button type="submit" form="camera-form" className="btn-primary" disabled={saving}>
            {saving ? <ArrowsClockwise size={18} className="animate-spin" aria-hidden="true" /> : <FloppyDisk size={18} aria-hidden="true" />}
            {isNew ? 'Guardar y conectar' : 'Guardar cambios'}
          </button>
        </>
      }
    >
      <form id="camera-form" onSubmit={save} noValidate className="grid gap-4 sm:grid-cols-2">
        {isNew && (
          <p className="flex gap-2 rounded-md bg-surface-2 p-3 text-[13px] text-fg-2 sm:col-span-2">
            <Info size={18} className="shrink-0 text-fg-3" aria-hidden="true" />
            La cámara necesita ONVIF activo y una regla de línea virtual configurada en su interfaz web.
          </p>
        )}
        <Field label="Nombre *" error={errors.name} className="sm:col-span-2">
          <input className="input" value={form.name} onChange={set('name')} placeholder="Ej. Puerta principal" aria-invalid={!!errors.name} />
        </Field>
        <Field label="Dirección IP *" error={errors.ip_address}>
          <input className="input num" value={form.ip_address} onChange={set('ip_address')} placeholder="192.168.1.100" inputMode="decimal" aria-invalid={!!errors.ip_address} />
        </Field>
        <Field label="Límite de personas" error={errors.max_capacity}>
          <input type="number" min="1" className="input num" value={form.max_capacity} onChange={set('max_capacity')} aria-invalid={!!errors.max_capacity} />
        </Field>
        <Field label="Tipo" hint={role?.hint} className="sm:col-span-2">
          <select className="input" value={form.role} onChange={set('role')}>
            {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </Field>
        <Field label="Zona" hint="Las cámaras con la misma zona suman su aforo.">
          <input className="input" value={form.zone} onChange={set('zone')} placeholder="Opcional" />
        </Field>
        <Field label="Ubicación">
          <input className="input" value={form.location} onChange={set('location')} placeholder="Opcional" />
        </Field>
        <Field label="Inicio de horario" error={errors.operating_hours_start}>
          <input type="time" className="input" value={form.operating_hours_start} onChange={set('operating_hours_start')} />
        </Field>
        <Field label="Fin de horario" error={errors.operating_hours_end}>
          <input type="time" className="input" value={form.operating_hours_end} onChange={set('operating_hours_end')} />
        </Field>
      </form>
    </Modal>
  )
}

function DiscoveryPanel({ onPick, onClose }) {
  const [state, setState] = useState({ scanning: true, results: null, error: null })

  useEffect(() => {
    let alive = true
    api.discoverCameras()
      .then((r) => alive && setState({ scanning: false, results: r?.data ?? [], error: null }))
      .catch((e) => alive && setState({ scanning: false, results: null, error: e.message }))
    return () => { alive = false }
  }, [])

  return (
    <Card className="mb-5">
      <CardHeader
        title="Cámaras encontradas en la red"
        subtitle={state.scanning ? 'Buscando por ONVIF y puertos abiertos. Puede tardar hasta 15 segundos.' : 'Elige una para agregarla.'}
        action={<button type="button" className="btn-ghost h-8 text-[13px]" onClick={onClose}>Cerrar</button>}
      />
      <div className="px-5 pb-5 pt-4">
        {state.scanning && (
          <p className="flex items-center gap-2 text-sm text-fg-2">
            <ArrowsClockwise size={18} className="animate-spin" aria-hidden="true" /> Escaneando…
          </p>
        )}
        {state.error && <p role="alert" className="text-sm text-danger">No se pudo escanear: {state.error}</p>}
        {state.results?.length === 0 && (
          <p className="text-sm text-fg-2">
            No apareció ninguna cámara. Revisa que estén encendidas, en la misma red que este equipo y con ONVIF activo.
          </p>
        )}
        {state.results?.length > 0 && (
          <ul className="divide-y divide-line rounded-md border border-line">
            {state.results.map((d) => (
              <li key={d.ip} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div>
                  <p className="num font-semibold">{d.ip}</p>
                  <p className="text-[13px] text-fg-2">{d.manufacturer} · {d.model} · puerto {d.port}</p>
                </div>
                {d.already_added
                  ? <StatusText icon={CheckCircle} tone="text-ok">Ya agregada</StatusText>
                  : <button type="button" className="btn-secondary h-8 text-[13px]" onClick={() => onPick(d)}><Plus size={16} aria-hidden="true" /> Agregar</button>}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}

function CamerasCard({ cameras, status, loaded, onEdit, onDeactivate }) {
  return (
    <Card>
      <CardHeader title="Cámaras" subtitle={loaded ? `${cameras.length} activa${cameras.length === 1 ? '' : 's'}` : 'Cargando…'} />
      {loaded && cameras.length === 0 ? (
        <EmptyState icon={VideoCamera} title="No hay cámaras">
          Usa “Buscar en la red” para encontrarlas o agrégalas a mano con su IP.
        </EmptyState>
      ) : (
        <div className="relative mt-4 overflow-x-auto">
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-y border-line bg-surface-2 text-left text-[13px] text-fg-2">
                <th scope="col" className="px-5 py-2.5 font-semibold">Cámara</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">IP</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Tipo</th>
                <th scope="col" className="px-3 py-2.5 text-right font-semibold">Límite</th>
                <th scope="col" className="px-3 py-2.5 font-semibold">Conexión</th>
                <th scope="col" className="px-5 py-2.5"><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {cameras.map((c) => {
                const conn = status[c.camera_id]
                const meta = connectionMeta(conn)
                return (
                  <tr key={c.id} className="align-top hover:bg-surface-2">
                    <td className="px-5 py-3">
                      <p className="font-semibold">{c.name}</p>
                      <p className="text-[13px] text-fg-2">{[c.zone && `Zona ${c.zone}`, c.location].filter(Boolean).join(' · ') || 'Sin zona'}</p>
                    </td>
                    <td className="num px-3 py-3">{c.ip_address}</td>
                    <td className="px-3 py-3">{roleLabel(c.role)}</td>
                    <td className="num px-3 py-3 text-right">{formatNumber(c.max_capacity)}</td>
                    <td className="max-w-[260px] px-3 py-3">
                      <StatusText icon={meta.icon} tone={meta.tone}>{meta.label}</StatusText>
                      {conn?.state === 'reconnecting' && conn.last_error && (
                        <p className="mt-0.5 text-[13px] text-fg-2">{conn.last_error}</p>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex justify-end gap-0.5">
                        <button type="button" className="icon-btn" onClick={() => onEdit(c)} aria-label={`Editar ${c.name}`} title="Editar">
                          <PencilSimple size={18} aria-hidden="true" />
                        </button>
                        <button type="button" className="icon-btn hover:text-danger" onClick={() => onDeactivate(c)} aria-label={`Desactivar ${c.name}`} title="Desactivar">
                          <Power size={18} aria-hidden="true" />
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function ThresholdsCard() {
  const { addToast } = useToast()
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.getSettings()
      .then((r) => setForm({ warning_threshold: r.data.warning_threshold, critical_threshold: r.data.critical_threshold }))
      .catch(() => setError('No se pudieron leer los umbrales.'))
  }, [])

  const save = async (e) => {
    e.preventDefault()
    const w = Number(form.warning_threshold)
    const c = Number(form.critical_threshold)
    if (!(w >= 1 && w <= 100)) return setError('La advertencia debe estar entre 1 y 100 %.')
    if (!(c >= 1 && c <= 200)) return setError('El crítico debe estar entre 1 y 200 %.')
    if (w >= c) return setError('La advertencia tiene que ser menor que el crítico.')
    setError(null)
    setSaving(true)
    try {
      await api.updateSettings({ warning_threshold: w, critical_threshold: c })
      addToast('Umbrales guardados', 'success')
    } catch (err) {
      addToast(`No se pudo guardar: ${err.message}`, 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card>
      <CardHeader title="Umbrales de aforo" subtitle="Porcentaje del límite de cada espacio" />
      {form && (
        <form onSubmit={save} className="space-y-4 px-5 pb-5 pt-4" noValidate>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Advertencia (%)">
              <input type="number" min="1" max="100" className="input num" value={form.warning_threshold}
                onChange={(e) => setForm((f) => ({ ...f, warning_threshold: e.target.value }))} />
            </Field>
            <Field label="Crítico (%)">
              <input type="number" min="1" max="200" className="input num" value={form.critical_threshold}
                onChange={(e) => setForm((f) => ({ ...f, critical_threshold: e.target.value }))} />
            </Field>
          </div>
          {error && <p role="alert" className="text-[13px] text-danger">{error}</p>}
          <button type="submit" className="btn-primary" disabled={saving}>
            <FloppyDisk size={18} aria-hidden="true" /> {saving ? 'Guardando…' : 'Guardar umbrales'}
          </button>
        </form>
      )}
      {!form && error && <p role="alert" className="px-5 pb-5 pt-4 text-sm text-danger">{error}</p>}
    </Card>
  )
}

export default function Settings() {
  const { cameras, status, loaded, refreshCameras } = useLive()
  const { addToast } = useToast()
  const [editing, setEditing] = useState(null)
  const [scanning, setScanning] = useState(false)
  const [deactivating, setDeactivating] = useState(null)

  const deactivate = async () => {
    const cam = deactivating
    setDeactivating(null)
    try {
      await api.deleteCamera(cam.id)
      addToast(`“${cam.name}” desactivada`, 'success')
      refreshCameras()
    } catch (e) {
      addToast(`No se pudo desactivar: ${e.message}`, 'error')
    }
  }

  return (
    <>
      <PageHeader title="Ajustes" subtitle="Cámaras conectadas y umbrales de alerta">
        <button type="button" className="btn-secondary" onClick={() => setScanning(true)} disabled={scanning}>
          <MagnifyingGlass size={18} aria-hidden="true" /> Buscar en la red
        </button>
        <button type="button" className="btn-primary" onClick={() => setEditing({})}>
          <Plus size={18} aria-hidden="true" /> Agregar cámara
        </button>
      </PageHeader>

      {scanning && <DiscoveryPanel onClose={() => setScanning(false)} onPick={(d) => setEditing(d)} />}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5 2xl:grid-cols-12">
        <div className="lg:col-span-2 2xl:col-span-8">
          <CamerasCard cameras={cameras} status={status} loaded={loaded} onEdit={setEditing} onDeactivate={setDeactivating} />
        </div>
        <div className="contents 2xl:block 2xl:col-span-4 2xl:space-y-5">
          <ThresholdsCard />
          <Card className="p-5">
            <h2 className="text-[17px] font-bold">Configuración del servidor</h2>
            <p className="mt-1.5 text-sm text-fg-2">
              El usuario y la contraseña de las cámaras, el intervalo de consulta, la zona horaria y el modo demo
              se definen en <code className="rounded-[4px] bg-surface-2 px-1 py-0.5 text-[13px]">backend/.env</code> y
              se aplican al reiniciar el backend.
            </p>
          </Card>
        </div>
      </div>

      {editing && (
        <CameraModal
          initial={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { refreshCameras(); setScanning(false) }}
        />
      )}

      {deactivating && (
        <Modal
          title="Desactivar cámara"
          onClose={() => setDeactivating(null)}
          width="max-w-md"
          footer={
            <>
              <button type="button" className="btn-secondary" onClick={() => setDeactivating(null)}>Cancelar</button>
              <button type="button" className="btn-danger" onClick={deactivate}>Desactivar</button>
            </>
          }
        >
          <p className="text-sm text-fg-2">
            <strong className="text-fg">{deactivating.name}</strong> dejará de contar. Sus datos históricos se conservan
            y puedes reactivarla agregándola otra vez con la misma IP.
          </p>
        </Modal>
      )}
    </>
  )
}
