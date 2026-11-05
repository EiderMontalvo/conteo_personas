import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import { CheckCircle, WarningCircle, Info, Warning, X } from '@phosphor-icons/react'

const ToastCtx = createContext(null)

const TYPES = {
  success: { icon: CheckCircle, cls: 'text-ok' },
  error: { icon: WarningCircle, cls: 'text-danger' },
  info: { icon: Info, cls: 'text-fg-2' },
  warning: { icon: Warning, cls: 'text-warn' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const remove = useCallback((id) => setToasts((prev) => prev.filter((t) => t.id !== id)), [])

  const addToast = useCallback((msg, type = 'info', duration = 4000) => {
    const id = ++idRef.current
    setToasts((prev) => [...prev, { id, msg, type }])
    setTimeout(() => remove(id), duration)
  }, [remove])

  const value = useMemo(() => ({ addToast }), [addToast])

  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
        {toasts.map((t) => {
          const { icon: Icon, cls } = TYPES[t.type] ?? TYPES.info
          return (
            <div key={t.id} className="pointer-events-auto flex items-start gap-3 rounded-md border border-line bg-surface px-4 py-3 text-sm shadow-float">
              <Icon size={18} weight="bold" className={`mt-px shrink-0 ${cls}`} aria-hidden="true" />
              <span className="flex-1">{t.msg}</span>
              <button type="button" aria-label="Cerrar aviso" onClick={() => remove(t.id)} className="-mr-1 text-fg-3 hover:text-fg">
                <X size={16} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastCtx.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export const useToast = () => useContext(ToastCtx)
