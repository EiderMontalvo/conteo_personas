// Cámaras con la misma `zone` forman un espacio: suman personas y totales, y el límite
// es el mayor max_capacity del grupo. Sin zona, cada cámara es su propio espacio.

export const claveZona = (esp) => esp.zone?.trim() || esp.name

export function agruparPorZona(espacios) {
  const grupos = new Map()
  for (const esp of espacios) {
    const zona = esp.zone?.trim() || null
    const key  = claveZona(esp)
    if (!grupos.has(key)) {
      grupos.set(key, {
        key,
        zona,
        esGrupo: false,
        name: key,
        cameraIds: [],
        max_capacity: 0,
        people_inside: 0,
        total_in: 0,
        total_out: 0,
      })
    }
    const g = grupos.get(key)
    g.cameraIds.push(esp.camera_id)
    g.esGrupo       = zona !== null && g.cameraIds.length > 1
    g.max_capacity  = Math.max(g.max_capacity, esp.max_capacity || 0)
    g.people_inside += esp.people_inside ?? 0
    g.total_in      += esp.total_in      ?? 0
    g.total_out     += esp.total_out     ?? 0
  }
  return [...grupos.values()]
}

/** Misma regla que el backend: pct ≥ crítico → 'Crítico', pct ≥ advertencia → 'Advertencia'. */
export function estadoAforo(peopleInside, maxCapacity, warnThreshold, critThreshold) {
  const maxCap = Math.max(maxCapacity || 0, 1)
  const pct    = Math.round((peopleInside / maxCap) * 100)
  return {
    pct,
    available: Math.max(0, maxCap - peopleInside),
    status: pct >= critThreshold ? 'Crítico' : pct >= warnThreshold ? 'Advertencia' : 'Normal',
  }
}
