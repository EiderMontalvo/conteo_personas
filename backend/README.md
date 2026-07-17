# Backend — Sistema de Conteo de Personas

Servicio Python (FastAPI) que recibe eventos de cruce de linea desde camaras Hanwha Wisenet XNO-6120R via protocolo ONVIF, los persiste en base de datos y los expone en tiempo real e historicamente a traves de una API REST y WebSocket.

---

## Indice

1. [Arquitectura](#arquitectura)
2. [Estructura de archivos](#estructura-de-archivos)
3. [Configuracion](#configuracion)
4. [Base de datos](#base-de-datos)
5. [API REST](#api-rest)
6. [WebSocket](#websocket)
7. [Gestion de camaras](#gestion-de-camaras)
8. [Estrategia de persistencia](#estrategia-de-persistencia)
9. [Ejecucion](#ejecucion)
10. [Dependencias](#dependencias)

---

## Arquitectura

El backend sigue una arquitectura en capas estricta. La regla de dependencia es unidireccional: `api` llama a `services`, `services` llama a `repositories` e `integrations`. Ninguna capa importa de la capa superior.

```
api/v1/          ->  services/        ->  repositories/
(routers)            (logica negocio)     (acceso BD)
                 ->  integrations/
                     (ONVIF, red)
```

### Componentes principales

**PollerPool** — Singleton que gestiona el ciclo de vida de todos los pollers ONVIF. Permite agregar, recargar y cancelar pollers en caliente sin reiniciar el servidor. Cuando el usuario edita la IP de una camara desde el frontend, `PollerPool.reload_camera()` cancela el poller actual y arranca uno nuevo con la nueva IP en el mismo ciclo de eventos.

**OnvifCameraClient** — Encapsula la conexion ONVIF PullPoint a una camara. Ejecuta el codigo zeep (sincrono) en un `ThreadPoolExecutor` para no bloquear el event loop de FastAPI. Soporta `reset(new_ip)` para reconectarse sin recrear el objeto.

**CountingService** — Unica fuente de verdad para la logica de roles (`both` / `in_only` / `out_only`), la decision de persistir `change_event` o `hourly_heartbeat`, y el broadcast WebSocket.

**EnvWriter** — Mantiene el archivo `.env` sincronizado con la base de datos. Cada escritura es atomica: escribe en `.env.tmp` y hace `os.replace()` para evitar corrupcion ante errores.

**ConnectionManager** — Gestiona las conexiones WebSocket activas y hace broadcast a todas ellas. Elimina silenciosamente las conexiones muertas.

---

## Estructura de archivos

```
backend/
├── .env                          <- Credenciales (no subir a git)
├── .env.example                  <- Plantilla de configuracion
├── requirements.txt
├── main.py                       <- Composition root (routers + lifespan + CORS)
├── database.py                   <- Motor SQLAlchemy y sesion
│
└── app/
    ├── core/
    │   ├── config.py             <- Settings via pydantic-settings (lee .env)
    │   └── logging.py            <- Configuracion de logging estructurado
    │
    ├── models/
    │   └── counting.py           <- Modelos ORM: Camera, CountingEvent,
    │                                CameraState, HourlyStat, SystemSettings
    │
    ├── schemas/
    │   ├── common.py             <- ApiResponse[T] — sobre estandar para toda la API
    │   ├── camera.py             <- CameraOut, CameraCreate, CameraUpdate, DiscoveredCamera
    │   └── settings.py           <- SystemSettingsOut, SystemSettingsUpdate
    │
    ├── repositories/
    │   ├── base.py               <- GenericRepository[T] con CRUD reutilizable
    │   ├── camera_repo.py        <- CameraRepository (seed, get_active, upsert_state)
    │   └── event_repo.py         <- EventRepository (add_event, get_historical, get_for_export)
    │
    ├── services/
    │   ├── camera_service.py     <- Orquesta BD + .env + PollerPool para el ciclo de vida de camaras
    │   ├── counting_service.py   <- Logica de roles, heartbeat y persistencia event-driven
    │   ├── env_writer.py         <- Escritura atomica del .env
    │   └── excel_service.py      <- Generacion y parseo de archivos Excel
    │
    ├── integrations/
    │   └── onvif/
    │       ├── client.py         <- OnvifCameraClient (zeep en ThreadPoolExecutor)
    │       ├── event_listener.py <- CameraPoller + PollerPool (gestion dinamica)
    │       └── discovery.py      <- Descubrimiento de camaras (WS-Discovery + TCP scan)
    │
    ├── websockets/
    │   └── connection_manager.py <- ConnectionManager singleton para broadcast WS
    │
    └── api/
        └── v1/
            ├── cameras.py        <- CRUD de camaras + endpoint /discover
            ├── analytics.py      <- Historico y resumen del dia
            ├── realtime.py       <- WebSocket /ws/live
            ├── excel.py          <- Exportar / importar Excel
            └── settings.py       <- Configuracion del sistema
```

---

## Configuracion

Copia `.env.example` a `.env` y edita los valores. El archivo `.env` nunca debe subirse al repositorio.

### Variables requeridas

| Variable | Descripcion | Ejemplo |
|---|---|---|
| `CAMERA_USER` | Usuario ONVIF compartido por todas las camaras | `admin` |
| `CAMERA_PASS` | Contrasena ONVIF | `tu_contrasena` |

### Variables opcionales con valor por defecto

| Variable | Descripcion | Defecto |
|---|---|---|
| `CAMERA_0_IP` | IP de la camara con indice 0 (semilla inicial) | — |
| `CAMERA_0_NAME` | Nombre descriptivo de la camara 0 | `Camara 0` |
| `CAMERA_0_ROLE` | Rol: `both` / `in_only` / `out_only` | `both` |
| `CAMERA_0_GROUP` | Grupo logico para consolidar camaras | — |
| `POLL_INTERVAL_SECONDS` | Intervalo de polling en segundos (minimo 2) | `3` |
| `DATABASE_URL` | URL de SQLAlchemy | `sqlite:///./conteo_personas.db` |
| `TIMEZONE` | Zona horaria IANA | `America/Lima` |
| `BUSINESS_HOUR_START` | Inicio del horario de negocio (0-24) | `0` |
| `BUSINESS_HOUR_END` | Fin del horario de negocio (0-24) | `24` |

### Semilla de camaras desde el .env

Las variables `CAMERA_{n}_*` del `.env` se usan como semilla **una sola vez**: cuando la tabla `cameras` de la base de datos esta vacia al arrancar el servidor por primera vez. A partir de ese momento, la base de datos es la fuente de verdad y el `.env` actua como backup sincronizado automaticamente cuando se editan camaras desde el frontend.

### Camaras con rol separado (misma puerta, dos camaras)

```dotenv
CAMERA_0_IP=192.168.1.100
CAMERA_0_NAME=Entrada_Principal
CAMERA_0_ROLE=in_only
CAMERA_0_GROUP=puerta_norte

CAMERA_1_IP=192.168.1.101
CAMERA_1_NAME=Salida_Principal
CAMERA_1_ROLE=out_only
CAMERA_1_GROUP=puerta_norte
```

Ambas camaras se consolidan en reportes y el export Excel como un solo punto identificado por `puerta_norte`.

---

## Base de datos

### Tablas

| Tabla | Descripcion |
|---|---|
| `cameras` | Configuracion de cada camara (IP, nombre, rol, aforo, horario). Fuente de verdad para el PollerPool. |
| `camera_states` | Estado en tiempo real: personas dentro, totales, estado de aforo. Se actualiza con cada cruce. |
| `counting_events` | Historico de eventos. Tipos: `change_event`, `hourly_heartbeat`, `imported`. |
| `hourly_stats` | Agregados por hora (bucket) para consultas de reportes rapidas. |
| `system_settings` | Configuracion editable desde el frontend: umbrales, zona horaria, intervalos. |

### Motores soportados

- **SQLite** (por defecto): sin instalacion adicional, archivo local `conteo_personas.db`.
- **PostgreSQL**: cambia `DATABASE_URL` en `.env`. No requiere cambios en el codigo.

---

## API REST

Todos los endpoints viven bajo `/api/v1/`. La respuesta tiene siempre la estructura:

```json
{
  "ok": true,
  "data": ...,
  "total": 5,
  "error": null
}
```

Documentacion interactiva disponible en `/docs` (Swagger UI) y `/redoc`.

### Camaras

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/v1/cameras` | Lista camaras activas con estado en tiempo real |
| `POST` | `/api/v1/cameras` | Crear camara nueva (actualiza BD y .env, arranca poller) |
| `GET` | `/api/v1/cameras/discover` | Escanear la red local para encontrar camaras ONVIF |
| `GET` | `/api/v1/cameras/{id}` | Detalle de una camara |
| `PUT` | `/api/v1/cameras/{id}` | Actualizar camara (si cambia IP, el poller se reconecta automaticamente) |
| `DELETE` | `/api/v1/cameras/{id}` | Desactivar camara y cancelar su poller |

### Analitica

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/v1/stats/historical` | Historico filtrable por camara, grupo y fechas |
| `GET` | `/api/v1/stats/summary` | Totales del dia en curso por camara |

Parametros de `/historical`:

| Parametro | Tipo | Descripcion |
|---|---|---|
| `camera_id` | int | Filtrar por camara |
| `group` | string | Filtrar por grupo logico |
| `date_from` | string | Fecha inicio `YYYY-MM-DD` |
| `date_to` | string | Fecha fin `YYYY-MM-DD` (inclusive) |
| `limit` | int | Maximo de registros (defecto 500, maximo 5000) |

### Excel

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/v1/excel/export` | Exportar datos a `.xlsx` |
| `POST` | `/api/v1/excel/import` | Importar desde `.xlsx` |

El archivo exportado agrupa los eventos por hora, calcula flujo neto y personas en local. Los timestamps se convierten a la zona horaria configurada en `TIMEZONE`.

Columnas requeridas para importacion: `Fecha`, `Hora`, `Entradas`, `Salidas`. Columnas opcionales: `Camara`, `Grupo`.

### Configuracion del sistema

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/v1/settings` | Obtener configuracion del sistema |
| `PUT` | `/api/v1/settings` | Actualizar configuracion del sistema |

### Retrocompatibilidad

Las rutas anteriores redirigen automaticamente a las nuevas:

| Ruta legacy | Redirige a |
|---|---|
| `/api/cameras` | `/api/v1/cameras` |
| `/api/cameras/config` | `/api/v1/cameras` |
| `/api/stats/historical` | `/api/v1/stats/historical` |
| `/api/settings` | `/api/v1/settings` |

---

## WebSocket

**Ruta:** `ws://localhost:8000/ws/live`

El servidor envia un mensaje cada vez que se detecta un cruce de linea. El cliente no necesita enviar nada; se mantiene la conexion viva recibiendo los mensajes.

### Formato de mensaje

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

| Campo | Descripcion |
|---|---|
| `in_count` | Cruces de entrada en este ciclo de polling |
| `out_count` | Cruces de salida en este ciclo de polling |
| `accum_in` | Total acumulado de entradas desde el arranque del servidor |
| `accum_out` | Total acumulado de salidas desde el arranque del servidor |

---

## Gestion de camaras

### Agregar una camara nueva desde el frontend

1. En el frontend, ir a **Ajustes -> Camaras -> Escanear Red**.
2. El backend ejecuta WS-Discovery (ONVIF estandar, UDP multicast puerto 3702).
3. Si WS-Discovery no encuentra nada, realiza un TCP scan del rango `/24` de la IP local.
4. Las camaras encontradas aparecen en una lista con su IP y modelo.
5. El usuario hace clic en **Agregar**, rellena nombre y rol, y guarda.
6. El backend inserta en BD, actualiza el `.env` y arranca el poller en ese mismo instante.

### Editar la IP de una camara existente

1. En el frontend, ir a **Ajustes -> Camaras -> (icono editar)**.
2. Cambiar el campo IP y guardar.
3. El backend actualiza la BD, reescribe la entrada correspondiente en el `.env` de forma atomica, y llama a `PollerPool.reload_camera()`.
4. El poller de esa camara se cancela y se reinicia con la nueva IP. Los demas pollers continuan sin interrupcion.

### Requisitos previos en la camara Hanwha

Antes de agregar una camara al sistema, configurar desde su interfaz web (`http://<ip-camara>`):

1. **IVA activo**: Configuracion > Analiticas > IVA > agregar regla de Cruce de Linea, definir las direcciones A-a-B (entrada) y B-a-A (salida).
2. **ONVIF habilitado**: Red > ONVIF > habilitar protocolo y crear usuario con las credenciales que se usaran en `.env`.
3. **Reglas de evento**: Evento > Reglas de evento > verificar que la linea virtual este habilitada para notificar.

La IP de red de la camara (la que tiene asignada en el switch) se configura desde la propia interfaz de la camara o por DHCP; el backend no puede cambiarla.

### Rutas API de la camara (Captura de eventos)

El backend interactua con la camara a traves del protocolo estandar **ONVIF**. Las rutas internas de la camara utilizadas son:

1. **Servicio base (Device Service)**: `http://<ip-camara>:<puerto>/onvif/device_service`
   - Se utiliza para autenticarse, obtener capacidades y descubrir los demas endpoints.
2. **Servicio de eventos (Event Service)**: `http://<ip-camara>:<puerto>/onvif/Events` (ruta comun, descubierta dinamicamente)
   - El backend llama a la accion `CreatePullPointSubscription` para iniciar la suscripcion a los eventos de analitica (IVA).
3. **PullPoint**: Ruta temporal creada por la suscripcion, a la cual el backend hace peticiones constantes (`PullMessages`) para recibir los eventos de cruce de linea en formato XML.

---

## Estrategia de persistencia

El sistema usa una estrategia event-driven para minimizar el espacio en disco:

- `change_event`: se guarda unicamente cuando alguien cruza la linea (hay actividad real).
- `hourly_heartbeat`: si no hay actividad durante 1 hora dentro del horario de negocio configurado, se guarda un registro con `in=0`, `out=0`. Esto preserva la continuidad temporal en los reportes sin desperdiciar espacio.
- `imported`: registros cargados desde un archivo Excel externo.

---

## Ejecucion

### Con el script del proyecto (recomendado)

Desde la raiz del proyecto:

```
Windows:  start.bat
Linux:    ./start.sh
```

### Manual

```bash
# Activar entorno virtual
source venv/bin/activate          # Linux/macOS
venv\Scripts\activate             # Windows

# Instalar dependencias
pip install -r backend/requirements.txt

# Iniciar servidor
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

El servidor queda disponible en `http://localhost:8000`. La documentacion Swagger en `http://localhost:8000/docs`.

---

## Dependencias

| Paquete | Uso |
|---|---|
| `fastapi` | Framework web asincrono |
| `uvicorn` | Servidor ASGI |
| `sqlalchemy` | ORM y acceso a base de datos |
| `pydantic` / `pydantic-settings` | Validacion de datos y configuracion |
| `onvif-zeep` | Cliente ONVIF PullPoint (zeep) |
| `WSDiscovery` | Descubrimiento de camaras via WS-Discovery |
| `httpx` | Cliente HTTP asincrono (para identificar camaras en TCP scan) |
| `openpyxl` | Generacion y lectura de archivos Excel |
| `pytz` | Manejo de zonas horarias |
| `python-dotenv` | Carga del archivo `.env` |
| `python-multipart` | Soporte de uploads en FastAPI |
