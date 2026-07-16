// src/components/Topbar.jsx
import { RefreshCw, Download } from 'lucide-react'
import { api } from '../hooks/useApi'

/**
 * @param {object} props
 * @param {string}   props.title
 * @param {string}   props.subtitle
 * @param {boolean}  props.connected
 * @param {ReactNode} props.children   – Acciones extra en el topbar
 * @param {function} [props.onRefresh]
 * @param {object}   [props.exportParams]
 */
export default function Topbar({ title, subtitle, connected, children, onRefresh, exportParams }) {
  const handleExport = () => {
    const url = api.exportExcelUrl(exportParams || {})
    window.open(url, '_blank')
  }

  return (
    <header className="page-header" style={{ padding: '1.5rem 1.5rem 0.5rem', marginBottom: '0.5rem' }}>
      <div className="flex flex-col">
        <h1 className="text-[2.25rem] font-extrabold text-gray-900 tracking-[-0.03em] mb-1">{title}</h1>
        {subtitle && <p className="text-gray-500 text-[0.95rem]">{subtitle}</p>}
      </div>

      <div className="page-header-actions">

        {children}

        {onRefresh && (
          <button type="button" className="btn btn-outline" onClick={onRefresh} title="Actualizar datos">
            <RefreshCw size={14} />
            Actualizar
          </button>
        )}

        {exportParams !== undefined && (
          <button type="button" className="btn btn-outline" onClick={handleExport}>
            <Download size={14} />
            Exportar reporte
          </button>
        )}
      </div>
    </header>
  )
}
