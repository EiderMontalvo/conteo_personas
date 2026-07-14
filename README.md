# Sistema de Business Intelligence y Conteo de Personas

Sistema local, liviano y escalable para monitorizar en tiempo real el flujo de personas usando **cámaras Hanwha Wisenet XNO-6120R** a través del protocolo **ONVIF** (Suscripción de Eventos).

Compatible con **Windows 10/11** y **Linux (Debian/Ubuntu/Arch)**.

---

## Índice

1. [Arquitectura del Sistema](#arquitectura-del-sistema)
2. [Requisitos Previos](#requisitos-previos)
3. [Configuración de la Cámara (Hanwha)](#configuración-de-la-cámara-hanwha)
4. [Instalación — Linux](#instalación--linux)
5. [Instalación — Windows](#instalación--windows)
6. [Configurar Credenciales (.env)](#configurar-credenciales-env)
7. [Iniciar el Sistema](#iniciar-el-sistema)
8. [API Endpoints](#api-endpoints)
9. [Estructura del Proyecto](#estructura-del-proyecto)
10. [Solución de Problemas](#solución-de-problemas)

---

## Arquitectura del Sistema

```
[Cámaras Wisenet] --PoE--> [Switch Dahua] --RTSP/ONVIF--> [NVR Uniview]
                                  |
                        ONVIF (Event Subscription)
                                  |
                 ┌────────────────────────────────────┐
                 │   Backend Python (FastAPI)          │
                 │   · polling asíncrono por cámara   │
                 │   · persistencia SQLite/PostgreSQL  │
                 │   · WebSocket + REST API            │
                 └────────────────────────────────────┘
                                  |
                     WebSocket (tiempo real) + REST
                                  |
                 ┌────────────────────────────────────┐
                 │   Frontend (Vanilla JS + Chart.js)  │
                 │   · Dashboard con selector cámara   │
                 │   · Gráficos en tiempo real         │
                 └────────────────────────────────────┘
```

---

## Requisitos Previos

| Componente | Versión mínima | Notas |
|------------|---------------|-------|
| Python | 3.9 | [python.org](https://www.python.org/downloads/) |
| Cámara Hanwha XNO-6120R | Firmware 2.x+ | Con analítica IVA configurada |
| Navegador | Chrome 90+ / Firefox 88+ | Para el Dashboard |
| Red | LAN / Wi-Fi | El equipo debe tener acceso a las IPs de las cámaras |

---

## Configuración de la Cámara (Hanwha)

Antes de ejecutar el sistema, la cámara debe estar configurada para que el backend pueda extraer los conteos.

### Paso 1 — Acceder a la interfaz web

Abre un navegador e ingresa a la IP de la cámara (ej. `http://192.168.1.100`).  
Inicia sesión con tu usuario y contraseña de administrador.

### Paso 2 — Verificar la tarjeta MicroSD (para estadísticas históricas)

La tarjeta MicroSD habilita el **motor de estadísticas nativo** de Wisenet, que acumula conteos históricos incluso si el backend se desconecta temporalmente.

1. Ve a **Configuración → Almacenamiento → Tarjeta SD**.
2. Verifica que el estado aparezca como `Montada` y el formato sea `EXT4`.
3. Si aparece como `No formateada`, haz clic en **Formatear** (esto borra el contenido de la tarjeta).

> **Nota:** La MicroSD es opcional para el funcionamiento en tiempo real del sistema, pero recomendada para disponer de estadísticas históricas en la propia cámara.

### Paso 3 — Configurar la línea virtual IVA (Conteo de personas)

El sistema lee los conteos de la función **IVA (Intelligent Video Analytics)** de la cámara.

1. Ve a **Configuración → Analíticas → IVA**.
2. Haz clic en **Agregar regla** y selecciona el tipo **Cruce de línea (Line Crossing)** o **Conteo de personas**.
3. Dibuja la línea virtual en la zona de interés (ej. puerta de entrada).
4. Configura las **Direcciones**:
   - `A → B`: cuenta como **Entrada**.
   - `B → A`: cuenta como **Salida**.
   - `A ↔ B`: cuenta ambas direcciones.
5. Asegúrate de que la regla esté **Habilitada** y guarda los cambios.

### Paso 4 — Habilitar Notificaciones ONVIF

Para que la cámara envíe los eventos en tiempo real a nuestro backend, es indispensable habilitar el protocolo ONVIF:

1. Ve a **Red → ONVIF**.
2. Habilita el protocolo ONVIF y crea un usuario (usa las mismas credenciales que pondrás en tu archivo `.env`).
3. Ve a **Evento → Reglas de evento** (Event Rules).
4. Asegúrate de que la "Línea virtual" esté habilitada y tenga permiso de notificar eventos.

---

## Instalación — Linux

### 1. Clonar o descargar el proyecto

```bash
# Con git:
git clone <url-del-repositorio> conteo_personas
cd conteo_personas

# O descomprime el ZIP y entra a la carpeta:
cd conteo_personas
```

### 2. Crear el entorno virtual e instalar dependencias

```bash
python3 -m venv venv
source venv/bin/activate

pip install -r backend/requirements.txt
```

### 3. Configurar credenciales

```bash
cp backend/.env.example backend/.env
nano backend/.env        # o usa tu editor preferido
```

Rellena `CAMERA_USER`, `CAMERA_PASS` y las IPs de tus cámaras. Ver la sección [Configurar Credenciales](#configurar-credenciales-env).

### 4. Iniciar el sistema

```bash
chmod +x start.sh   # solo la primera vez
./start.sh
```

El script levanta **automáticamente** el backend (puerto 8000) y el frontend (puerto 3001).  
Abre tu navegador en: **http://localhost:3001**

---

## Instalación — Windows

### 1. Instalar Python

1. Descarga Python 3.11+ desde [python.org](https://www.python.org/downloads/).
2. Durante la instalación, **marca la casilla "Add Python to PATH"** (muy importante).
3. Verifica la instalación abriendo `CMD` o `PowerShell` y escribiendo:
   ```
   python --version
   ```

### 2. Descargar el proyecto

Descarga y descomprime el ZIP del proyecto, o clónalo con git si lo tienes instalado:

```powershell
git clone <url-del-repositorio> conteo_personas
cd conteo_personas
```

### 3. Configurar credenciales

Abre el Explorador de Archivos, ve a la carpeta `backend\` y copia el archivo `.env.example`:

```cmd
copy backend\.env.example backend\.env
```

Luego abre `backend\.env` con el Bloc de Notas y rellena tus datos.  
Ver la sección [Configurar Credenciales](#configurar-credenciales-env).

### 4. Iniciar el sistema

Simplemente **haz doble clic en `start.bat`** desde el Explorador de Archivos.

El script realizará automáticamente:
- Crear el entorno virtual Python
- Instalar todas las dependencias
- Verificar que el `.env` existe
- Levantar el backend y el frontend en paralelo

Abre tu navegador en: **http://localhost:3001**

> **Nota Windows:** Si aparece una advertencia de SmartScreen, haz clic en "Más información" → "Ejecutar de todas formas". Es un `.bat` local, no un archivo descargado de internet.

---

## Configurar Credenciales (.env)

Edita el archivo `backend/.env` (nunca subas este archivo a git):

```dotenv
# ── Credenciales (compartidas por todas las cámaras) ────────
CAMERA_USER=[USER]
CAMERA_PASS=[PASSWORD]

# ── Definición de cámaras ───────────────────────────────────
# El sistema detecta automáticamente todas las CAMERA_N_IP definidas.
# Puedes agregar o quitar bloques según cuántas cámaras tengas.

CAMERA_0_IP=192.168.1.100
CAMERA_0_NAME=Entrada Principal

CAMERA_1_IP=192.168.1.101
CAMERA_1_NAME=Salida Lateral

CAMERA_2_IP=192.168.1.102
CAMERA_2_NAME=Pasillo Central

CAMERA_3_IP=192.168.1.103
CAMERA_3_NAME=Acceso Bodega

# ── Polling ──────────────────────────────────────────────────
# Intervalo de consulta a la cámara en segundos.
# No bajar de 2 para no saturar la CPU de la cámara.
POLL_INTERVAL_SECONDS=3

# ── Base de datos ────────────────────────────────────────────
# SQLite (por defecto, no requiere instalar nada extra):
DATABASE_URL=sqlite:///./conteo_personas.db

# PostgreSQL (opcional, para producción / ML a futuro):
# DATABASE_URL=postgresql://usuario:contraseña@localhost/conteo_personas
```

---

## Iniciar el Sistema

### Método rápido (recomendado)

| Sistema | Comando |
|---------|---------|
| **Linux / macOS** | `./start.sh` |
| **Windows** | Doble clic en `start.bat` |

### Método manual

Si prefieres iniciar cada componente por separado:

**Linux:**
```bash
# Terminal 1 - Backend
source venv/bin/activate
cd backend
python main.py

# Terminal 2 - Frontend
cd frontend
python3 -m http.server 3001
```

**Windows (CMD):**
```cmd
REM Terminal 1 - Backend
venv\Scripts\python.exe backend\main.py

REM Terminal 2 - Frontend
venv\Scripts\python.exe -m http.server 3001 --directory frontend
```

**Acceso al Dashboard:** http://localhost:3001

---

## API Endpoints

Con el backend corriendo, puedes acceder a la documentación interactiva en **http://localhost:8000/docs**.

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/cameras` | Lista las cámaras configuradas |
| `GET` | `/api/stats/historical` | Histórico de eventos (filtrable por `camera_id` y `limit`) |
| `WS` | `/ws/live` | Stream WebSocket en tiempo real (todas las cámaras) |
| `GET` | `/docs` | Swagger UI — Documentación interactiva |

---

## Estructura del Proyecto

```
conteo_personas/
├── start.sh                ← Inicio rápido en Linux/macOS
├── start.bat               ← Inicio rápido en Windows
├── .gitignore
├── README.md
│
├── backend/
│   ├── .env                ← Credenciales (NO subir a git)
│   ├── .env.example        ← Plantilla de configuración
│   ├── requirements.txt
│   ├── config.py           ← Carga .env, tipado fuerte, singleton
│   ├── database.py         ← Motor SQLAlchemy (SQLite / PostgreSQL)
│   ├── models.py           ← Tablas ORM
│   ├── schemas.py          ← Validación Pydantic
│   ├── sunapi.py           ← Cliente ONVIF (Zeep) para suscripción de eventos
│   ├── poller.py           ← Demonio multi-cámara asíncrono
│   └── main.py             ← FastAPI (REST + WebSockets + ciclo de vida)
│
└── frontend/
    ├── index.html
    ├── css/
    │   └── style.css
    └── js/
        └── app.js
```

---

## Solución de Problemas

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| `Error de conexión con la cámara X.X.X.X` | IP incorrecta o cámara apagada | Haz `ping 192.168.1.100` desde tu equipo. Si falla, revisa la red. |
| El conteo se queda en 0 | Evento no asignado en ONVIF | Revisa "Event Rules" en la cámara y asegúrate de que la línea virtual esté activa. |
| `python: command not found` (Linux) | Python 3 no instalado | Instala con `sudo apt install python3 python3-venv python3-pip` |
| `pip: No existe el fichero` | venv corrupto | Elimina la carpeta `venv/` y vuelve a ejecutar `start.sh` o `start.bat`. |
| `Address already in use` | El puerto ya está en uso | Cambia el puerto del frontend en el script (`3001` → `3002`, etc.) |
| SmartScreen bloquea `start.bat` | Windows Defender | Haz clic derecho en `start.bat` → Propiedades → Desbloquear. |
| Dashboard muestra "Desconectado" | Backend no corriendo o error de CORS | Verifica que `main.py` esté ejecutándose y no haya errores en su consola. |
