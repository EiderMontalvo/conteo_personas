// src/hooks/useApi.js
// URL vacía = relativa, el proxy de Vite redirige /api → http://localhost:8000/api
const BASE = ''

export const api = {
  getCameras: () =>
    fetch(`${BASE}/api/cameras`).then(r => r.json()),

  getHistorical: (params = {}) => {
    const q = new URLSearchParams()
    if (params.cameraId) q.set('camera_id', params.cameraId)
    if (params.group) q.set('group', params.group)
    if (params.limit) q.set('limit', params.limit)
    return fetch(`${BASE}/api/stats/historical?${q}`).then(r => r.json())
  },

  exportExcelUrl: (params = {}) => {
    const q = new URLSearchParams()
    if (params.dateFrom) q.set('date_from', params.dateFrom)
    if (params.dateTo) q.set('date_to', params.dateTo)
    if (params.cameraId) q.set('camera_id', params.cameraId)
    if (params.group) q.set('group', params.group)
    return `${BASE}/api/export/excel?${q}`
  },

  importExcel: async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${BASE}/api/import/excel`, { method: 'POST', body: fd })
    return r.json()
  },
}
