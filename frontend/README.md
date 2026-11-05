# Frontend — Sistema de Conteo de Personas

Dashboard web en **React 19 + Vite 8** que consume la API REST y el WebSocket del backend FastAPI para mostrar en tiempo real el flujo de personas, la analítica histórica y el control de aforo.

---

## Indice

1. [Stack](#stack)
2. [Arquitectura](#arquitectura)
3. [Estructura de archivos](#estructura-de-archivos)
4. [Requisitos previos](#requisitos-previos)
5. [Puesta en marcha](#puesta-en-marcha)
6. [Comandos](#comandos)
7. [Proxy del dev server](#proxy-del-dev-server)
8. [Rutas y paginas](#rutas-y-paginas)
9. [Datos: hooks y API](#datos-hooks-y-api)
10. [WebSocket en tiempo real](#websocket-en-tiempo-real)
11. [Estilos con Tailwind](#estilos-con-tailwind)
12. [Contrato con el backend](#contrato-con-el-backend)
13. [Convenciones](#convenciones)
14. [Solucion de problemas](#solucion-de-problemas)

---

## Stack

| Paquete | Version | Uso |
|---|---|---|
| `react` | ^19.2 | UI (sin clases, solo hooks) |
| `react-dom` | ^19.2 | Render |
| `react-router-dom` | ^7.18 | Enrutado SPA |
| `recharts` | ^3.9 | Graficas de area, barras, lineas |
| `lucide-react` | ^1.24 | Iconografia |
| `vite` | ^8.1 | Bundler + dev server |
| `@vitejs/plugin-react` | ^6.0 | Compilador de React |
| `tailwindcss` | ^3.4 | Estilos utility-first |
| `autoprefixer` / `postcss` | — | Pipeline de Tailwind |
| `oxlint` | ^1.71 | Linter (NO eslint) |

**JSX puro:** no se usa TypeScript ni PropTypes. La validacion de API corre en el backend (Pydantic).

---

## Arquitectura

Aplicacion SPA de una sola pagina. El `main.jsx` monta `<App />` dentro de `<ToastProvider>`. `App.jsx` declara el layout (`Sidebar` + area principal) y las rutas con `react-router-dom` v7.

```
index.html
  └── src/main.jsx
        └── App.jsx                                <- layout + <Routes>
              ├── components/Sidebar.jsx            <- navegacion + estado de conexion WS
              ├── components/Topbar.jsx             <- barra superior reutilizable
              └── pages/                            <- una pagina por ruta
                    ├── Dashboard.jsx              <- tiempo real
                    ├── Analytics.jsx              <- historico
                    ├── CapacityControl.jsx        <- aforo (role=space)
                    └── Settings.jsx               <- camaras + sistema
```

El fetching y la conexion WebSocket viven en `hooks/`, **no** en el JSX del componente. Los componentes solo consumen el resultado.

---

## Estructura de archivos

```
frontend/
├── index.html                     <- <div id="root"> + script /src/main.jsx
├── package.json
├── vite.config.js                 <- dev server :3000 + proxy a :8000
├── tailwind.config.js             <- tokens de color/sombra/radius
├── postcss.config.js
└── src/
    ├── main.jsx                   <- entry: ReactDOM.createRoot
    ├── App.jsx                    <- router + layout
    ├── index.css                  <- directivas Tailwind + estilos base
    │
    ├── pages/                     <- una pagina por ruta
    │   ├── Dashboard.jsx
    │   ├── Analytics.jsx
    │   ├── CapacityControl.jsx
    │   └── Settings.jsx
    │
    ├── components/                <- compartidos entre 2+ paginas
    │   ├── Sidebar.jsx
    │   └── Topbar.jsx
    │
    ├── context/
    │   └── ToastContext.jsx       <- notificaciones effimeras (useToast)
    │
    ├── hooks/                     <- TODO el fetching aqui
    │   ├── useApi.js              <- cliente REST relativo (/api/v1/...)
    │   ├── useFetch.js            <- hook generico de fetching (data/loading/error)
    │   └── useWebSocket.js        <- conexion WS persistente + reconexion
    │
    └── assets/
        ├── hero.png
        └── vite.svg
```

> **Regla de subida:** si un componente se usa en 2 o mas paginas, sube de `pages/` a `components/`.

---

## Requisitos previos

| Componente | Version minima | Notas |
|---|---|---|
| Node.js | 18 | Recomendado 20+ |
| npm | 9+ | Viene con Node |
| Backend FastAPI | — | Debe correr en `http://localhost:8000` durante el desarrollo |

El frontend **no funciona standalone**: necesita el backend levantado para servir `/api` y `/ws`.

---

## Puesta en marcha

### Con el script del proyecto (recomendado)

Desde la raiz del monorepo:

```
Windows:  start.bat
Linux:    ./start.sh
```

El script levanta backend y frontend juntos. El dashboard queda en `http://localhost:3001`.

### Solo el frontend

```bash
cd frontend
npm install
npm run dev
```

Dev server en `http://localhost:3000` con proxy a `http://localhost:8000` para `/api` y `/ws`.

### Build de produccion

```bash
npm run build      # genera dist/
npm run preview    # sirve el build localmente
```

---

## Comandos

| Comando | Descripcion |
|---|---|
| `npm run dev` | Dev server en `:3000` con HMR y proxy a `:8000` |
| `npm run build` | Build de produccion a `dist/` |
| `npm run preview` | Sirve el build local |
| `npm run lint` | Oxlint (NO eslint) |
| `npm run doctor` | Triaje con `npx react-doctor@latest` |

Orden recomendado al cerrar una tarea: **`lint` -> `build`**.

### Reglas activas de oxlint

- `react/rules-of-hooks: error`
- `react/only-export-components: warn`

---

## Proxy del dev server

`vite.config.js` configura el proxy:

```js
server: {
  port: 3000,
  proxy: {
    '/api': { target: 'http://localhost:8000', changeOrigin: true },
    '/ws':  { target: 'ws://localhost:8000', ws: true },
  },
}
```

Por eso **las URLs del codigo van relativas** (`/api/v1/...`). Nunca hardcodear `http://localhost:8000` en codigo de produccion.

> Excepcion: `useWebSocket.js` se conecta directamente a `ws://localhost:8000/ws/live` porque el proxy WS de Vite en algunos entornos no es fiable en dev. En el script unificado (`start.bat`) el frontend se sirve en `:3001` y el WS reacha al backend tambien por el puerto directo.

---

## Rutas y paginas

Definidas en `App.jsx` con `react-router-dom` v7:

| Ruta | Pagina | Descripcion |
|---|---|---|
| `/` | `Dashboard.jsx` | Contadores en tiempo real y estado de cada camara |
| `/analytics` | `Analytics.jsx` | Historico, graficas y exportacion Excel |
| `/aforo` | `CapacityControl.jsx` | Panel de aforo (camaras con `role=space`) |
| `/settings` | `Settings.jsx` | Configuracion de camaras y del sistema |
| `*` | — | Redirige a `/` |

La navegacion vive en `components/Sidebar.jsx`, que ademas muestra el estado de la conexion WebSocket (`Sistema en Linea` / `Desconectado`) y reloj con la hora local.

---

## Datos: hooks y API

### `useApi.js`

ClienteRest minimalista con URL base vacia (relativa). Expone un objeto `api`:

```js
import { api } from '../hooks/useApi'

api.getCameras()                    // GET /api/v1/cameras
api.createCamera(data)              // POST /api/v1/cameras
api.updateCamera(id, data)          // PUT  /api/v1/cameras/{id}
api.deleteCamera(id)                // DELETE /api/v1/cameras/{id}
api.discoverCameras()               // GET /api/v1/cameras/discover
api.getHistorical({ cameraId, group, dateFrom, dateTo, limit })  // GET /api/v1/stats/historical
api.getSummary()                    // GET /api/v1/stats/summary
api.getCapacity()                   // GET /api/v1/stats/capacity
api.getSettings()                   // GET /api/v1/settings
api.updateSettings(data)            // PUT /api/v1/settings
api.exportExcel({ dateFrom, dateTo, cameraId, group })  // GET /api/v1/excel/export (descarga blob)
api.importExcel(file)               // POST /api/v1/excel/import (multipart)
```

Todos los fetch pasan por `checkOk(response)` antes de `r.json()`, de modo que un HTTP 4xx/5xx lanza un `Error` descriptivo en vez de resolverse como exito. Cada pagina captura el error y lo muestra via `useToast`.

### `useFetch.js`

Hook generico para cualquier llamada async con cache local, estado de carga y error. Internamente gestiona un `AbortController` por invocacion para evitar setState despues de unmount.

```js
import { useFetch } from '../hooks/useFetch'
import { api } from '../hooks/useApi'

const { data, loading, error } = useFetch(() => api.getCapacity(), [])
```

Patron: `useFetch(fetcher, deps)` donde `fetcher` es una funcion que devuelve una promesa y `deps` reinicia el efecto cuando cambian (como `useEffect`). El frontend lo usa para cargar datos declarativos sin escribir `useEffect` a mano en cada pagina.

### `useWebSocket.js`

Hook que mantiene una conexion persistente a `ws://localhost:8000/ws/live` con reconexion automatica cada 3 segundos:

```js
const { connected } = useWebSocket((data) => {
  // data = { type: "count_update", payload: {...} }
})
```

`useWebSocket(onMessage)` usa una ref interna para el callback, de modo que cambiar `onMessage` no reinicia la conexion. El estado `connected` se actualiza onopen/onclose.

---

## WebSocket en tiempo real

El backend envia mensajes con la forma:

```json
{
  "type": "count_update",
  "payload": {
    "camera_id": 0,
    "camera_name": "Puerta Principal",
    "group": null,
    "timestamp": "2026-07-17T15:00:00+00:00",
    "in_count": 1,
    "out_count": 0,
    "accum_in": 12,
    "accum_out": 8
  }
}
```

Los `type` los define el backend; el frontend solo los consume y los reenvia a traves del callback de `useWebSocket`. Para mantener los tipos centralizados, evita inventar strings nuevos en el frontend: si necesitas un tipo nuevo, habilito primero en el backend.

---

## Estilos con Tailwind

Tailwind v3 con tokens extendidos en `tailwind.config.js`.

### Tokens principales

| Token | Uso |
|---|---|
| `color.teal` / `color.teal.dark` / `color.teal.soft` | Color primario (header, sidebar, acentos) |
| `color.amber` / `color.amber.dark` / `color.amber.soft` | Estado Advertencia |
| `color.green` / `color.green.soft` | Estado Normal / OK |
| `color.red` / `color.red.soft` | Estado Critico / error |
| `color.purple` / `color.blue` | Acentos de graficas y categorias |
| `color.surface` / `color.surface.2` | Tarjetas y fondo de tarjetas |
| `color.body` | Fondo de la aplicacion |
| `color.sidebar` | Fondo del sidebar |
| `color.muted` / `color.xmuted` | Texto secundario / deshabilitado |
| `fontFamily.sans` | `Outfit` con fallback a `system-ui` |
| `boxShadow.xs / sm / md / lg` | Sombras de tarjetas |
| `borderRadius.sm / DEFAULT / lg / xl` | Radios de tarjetas y botones |

### Reglas

- **Cero colores/spacing hardcodeados**. Si un valor es unico y se repite, se promueve a token.
- Sin clases arbitrarias del tipo `w-[123px]` o `text-[#3b82f6]` si existe token equivalente.
- Si un patron de clases se repite 3+ veces, se extrae componente (NO `@apply`).
- Sin `style={{...}}` con valores fijos.

---

## Contrato con el backend

### Respuesta API estandar

Toda respuesta REST sigue el shape `ApiResponse[T]` del backend:

```json
{ "ok": true, "data": ..., "total": 0, "error": null }
```

El frontend NO envuelve los datos; asume que ok=true y consume `data` directamente.

### Endpoints consumidos

| Endpoint | Componente |
|---|---|
| `GET /api/v1/cameras` | Dashboard, Settings, Analytics |
| `GET /api/v1/cameras/discover` | Settings (Escanear Red) |
| `POST /api/v1/cameras` | Settings (Agregar camara) |
| `PUT /api/v1/cameras/{id}` | Settings (Editar IP / rol / aforo) |
| `DELETE /api/v1/cameras/{id}` | Settings (Desactivar) |
| `GET /api/v1/stats/historical` | Analytics |
| `GET /api/v1/stats/summary` | Dashboard |
| `GET /api/v1/stats/capacity` | CapacityControl |
| `GET /api/v1/excel/export` | Analytics (export) |
| `POST /api/v1/excel/import` | Settings o Analytics (import) |
| `GET /api/v1/settings` | Settings |
| `PUT /api/v1/settings` | Settings |
| `WS /ws/live` | Sidebar, Dashboard, CapacityControl |

Para detalle de cada endpoint, ver [`backend/README.md`](../backend/README.md).

---

## Convenciones

- **JSX puro**, sin TypeScript ni PropTypes.
- Componentes funcionales + hooks. Sin clases.
- La logica de negocio, fetching y efectos van en `hooks/`, nunca en el JSX.
- Composicion sobre herencia (`children`, render props).
- `React.memo` / `useMemo` / `useCallback` solo con razon medible (listas grandes, renders costosos), no por costumbre.
- Comentarios, nombres de variables y mensajes en español, consistente con el resto del repo.
- Antes de crear un hook o componente nuevo, `grep`/`glob` en `src/hooks/` y `src/components/` — reusar antes que crear.

---

## Solucion de problemas

| Problema | Causa probable | Solucion |
|---|---|---|
| El dashboard carga pero todo dice "Desconectado" | Backend no levantado | Levantar el backend primero: `cd backend && uvicorn main:app --reload` (con venv activo) |
| `useApi` devuelve `undefined` o error 404 | El dev server no esta en `:3000` o el backend no responde | Verificar que `vite.config.js` tenga el proxy y que el backend escuche en `:8000` |
| Export Excel falla | URLs relativas mal o el backend cambio de prefijo | Revisar `useApi.js#exportExcel` y comparar con `GET /api/v1/excel/export` del backend |
| Cambios de CSS no aplican | Tailwind no regenero | Reiniciar `npm run dev` o revisar `content:` en `tailwind.config.js` |
| Sidebar muestra "Desconectado" aunque la API responde | WS en `ws://localhost:8000/ws/live` caido | Verificar WebSocket en DevTools > Network, el backend debe tener `/ws/live` sin prefijo |
| `npm run lint` falla por hooks | Violacion de `react/rules-of-hooks` | Revisar orden/condicionales de `useEffect`, `useState` y hooks custom |
| Linter reporta exportaciones mixtas | `react/only-export-components: warn` | Separar constantes/hooks del mismo archivo del componente, o moverlos a `hooks/` |