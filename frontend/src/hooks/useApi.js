// Rutas relativas: el proxy de Vite envía /api al backend en :8000.
const BASE = ''

// fetch() no falla con 4xx/5xx; todas las llamadas pasan por aquí antes de leer el cuerpo.
async function checkOk(response) {
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`HTTP ${response.status}: ${text || response.statusText}`)
  }
  return response
}

function buildQuery(params = {}) {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') q.set(k, v)
  })
  return q.toString()
}

export const api = {

  getCameras: () =>
    fetch(`${BASE}/api/v1/cameras`)
      .then(checkOk)
      .then(r => r.json()),

  createCamera: (data) =>
    fetch(`${BASE}/api/v1/cameras`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(checkOk).then(r => r.json()),

  updateCamera: (id, data) =>
    fetch(`${BASE}/api/v1/cameras/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(checkOk).then(r => r.json()),

  /** Baja lógica; `id` es la PK de BD, no el camera_id. */
  deleteCamera: (id) =>
    fetch(`${BASE}/api/v1/cameras/${id}`, { method: 'DELETE' })
      .then(checkOk)
      .then(r => r.json()),

  getCameraStatus: () =>
    fetch(`${BASE}/api/v1/cameras/status`)
      .then(checkOk)
      .then(r => r.json()),

  discoverCameras: () =>
    fetch(`${BASE}/api/v1/cameras/discover`)
      .then(checkOk)
      .then(r => r.json()),

  /** Fechas 'YYYY-MM-DD' en día local; el backend las interpreta en su zona horaria. */
  getHistorical: (params = {}) => {
    const q = buildQuery({
      camera_id: params.cameraId,
      group:     params.group,
      date_from: params.dateFrom,
      date_to:   params.dateTo,
      limit:     params.limit,
    })
    return fetch(`${BASE}/api/v1/stats/historical${q ? '?' + q : ''}`)
      .then(checkOk)
      .then(r => r.json())
  },

  getSummary: () =>
    fetch(`${BASE}/api/v1/stats/summary`)
      .then(checkOk)
      .then(r => r.json()),

  getCapacity: () =>
    fetch(`${BASE}/api/v1/stats/capacity`)
      .then(checkOk)
      .then(r => r.json()),

  getHistoricalRange: () =>
    fetch(`${BASE}/api/v1/stats/range`)
      .then(checkOk)
      .then(r => r.json()),

  getSettings: () =>
    fetch(`${BASE}/api/v1/settings`)
      .then(checkOk)
      .then(r => r.json()),

  updateSettings: (data) =>
    fetch(`${BASE}/api/v1/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(checkOk).then(r => r.json()),

  /** Descarga vía Blob (no window.open) para poder detectar errores HTTP. */
  exportExcel: async (params = {}) => {
    const q = buildQuery({
      date_from:  params.dateFrom,
      date_to:    params.dateTo,
      camera_id:  params.cameraId,
      group:      params.group,
    })
    const url = `${BASE}/api/v1/excel/export${q ? '?' + q : ''}`
    const response = await fetch(url)
    await checkOk(response)
    const blob = await response.blob()
    const filename = [
      'conteo',
      params.dateFrom || 'inicio',
      params.dateTo   || 'hoy',
    ].join('_') + '.xlsx'
    const href = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = href
    a.download = filename
    a.rel = 'noopener noreferrer'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(href)
  },

  importExcel: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/api/v1/excel/import`, { method: 'POST', body: fd })
    await checkOk(r)
    return r.json()
  },

  /** Borra registros importados repetidos (misma cámara y mismo segundo). */
  purgeDuplicates: async () => {
    const r = await fetch(`${BASE}/api/v1/excel/purge-duplicates`, { method: 'POST' })
    await checkOk(r)
    return r.json()
  },
}
