// src/context/ToastContext.jsx
import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { CheckCircle, XCircle, Info, AlertTriangle, X } from 'lucide-react'

const ToastCtx = createContext(null)

const ICONS = {
  success: <CheckCircle size={15} />,
  error:   <XCircle     size={15} />,
  info:    <Info        size={15} />,
  warning: <AlertTriangle size={15} />,
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const addToast = useCallback((msg, type = 'info', duration = 3500) => {
    const id = ++idRef.current
    setToasts(prev => [...prev, { id, msg, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, duration)
  }, [])

  const remove = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const contextValue = useMemo(() => ({ addToast }), [addToast])

  return (
    <ToastCtx.Provider value={contextValue}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast ${t.type}`}>
            {ICONS[t.type]}
            <span style={{ flex: 1 }}>{t.msg}</span>
            <button type="button"
              aria-label="Cerrar"
              onClick={() => remove(t.id)}
              style={{ background:'none', border:'none', color:'inherit', cursor:'pointer', padding:0, display:'flex' }}
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useToast = () => useContext(ToastCtx)
