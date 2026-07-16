# Sistema de Business Intelligence y Conteo de Personas

Sistema local, liviano y escalable para monitorizar en tiempo real el flujo de personas usando **camaras Hanwha Wisenet XNO-6120R** a traves del protocolo **ONVIF** (Suscripcion de Eventos).

Compatible con **Windows 10/11** y **Linux (Debian/Ubuntu/Arch)**.

---

## Indice

1. [Arquitectura del Sistema](#arquitectura-del-sistema)
2. [Requisitos Previos](#requisitos-previos)
3. [Configuracion de la Camara (Hanwha)](#configuracion-de-la-camara-hanwha)
4. [Instalacion — Linux](#instalacion--linux)
5. [Instalacion — Windows](#instalacion--windows)
6. [Configurar Credenciales (.env)](#configurar-credenciales-env)
7. [Iniciar el Sistema](#iniciar-el-sistema)
8. [API Endpoints](#api-endpoints)
9. [Estructura del Proyecto](#estructura-del-proyecto)
10. [Solucion de Problemas](#solucion-de-problemas)

---

## Arquitectura del Sistema

```
[Camaras Wisenet] --PoE--> [Switch] --ONVIF Event Subscription-->
                                   |
                  +--------------------------------------------+
                  |   Backend Python (FastAPI)                  |
                  |   - Polling asincrono por camara            |
                  |   - Persistencia event-driven (SQLite/PG)  |
                  |   - WebSocket + REST API                    |
                  |   - Exportacion / Importacion Excel         |
                  +--------------------------------------------+
                                   |
                  WebSocket (tiempo real) + REST
                                   |
                  +--------------------------------------------+
                  |   Frontend (Vanilla JS + Chart.js)          |
                  |   - Dashboard tiempo real                   |
                  |   - Dashboard de analitica historica        |
                  |   - Exportar / Importar .xlsx               |
                  +--------------------------------------------+
```

### Estrategia de almacenamiento

El sistema usa una estrategia **event-driven** para minimizar el espacio en disco:

- **change_event**: se guarda unicamente cuando los conteos cambian (alguien cruza la linea).
- **hourly_heartbeat**: si no hay actividad, se guarda un registro por hora dentro del horario de negocio configurado. Esto preserva la continuidad temporal en los reportes sin desperdiciar espacio.
- **imported**: registros cargados desde un archivo Excel externo.

### Soporte de camaras por rol

Cuando la entrada y la salida estan en puntos fisicos distintos:

```dotenv
CAMERA_0_ROLE=in_only
CAMERA_0_GROUP=puerta_principal

CAMERA_1_ROLE=out_only
CAMERA_1_GROUP=puerta_principal
```

Ambas camaras se consolidan como un solo punto en los reportes y el Excel exportado.

---

## Requisitos Previos

| Componente | Version minima | Notas |
|------------|---------------|-------|
| Python | 3.9 | [python.org](https://www.python.org/downloads/) |
| Camara Hanwha XNO-6120R | Firmware 2.x+ | Con analitica IVA configurada |
| Navegador | Chrome 90+ / Firefox 88+ | Para el Dashboard |
| Red | LAN | El equipo debe tener acceso a las IPs de las camaras |

---

## Configuracion de la Camara (Hanwha)

### Paso 1 — Acceder a la interfaz web

Abre un navegador e ingresa a la IP de la camara (ej. `http://192.168.1.100`).
Inicia sesion con tu usuario y contrasena de administrador.

### Paso 2 — Verificar la tarjeta MicroSD (opcional)

La tarjeta MicroSD habilita el motor de estadisticas nativo de Wisenet, que acumula conteos historicos incluso si el backend se desconecta temporalmente.

1. Ve a **Configuracion > Almacenamiento > Tarjeta SD**.
2. Verifica que el estado aparezca como `Montada` y el formato sea `EXT4`.
3. Si aparece como `No formateada`, haz clic en **Formatear** (esto borra el contenido de la tarjeta).

> La MicroSD es opcional para el funcionamiento en tiempo real del sistema.

### Paso 3 — Configurar la linea virtual IVA

1. Ve a **Configuracion > Analiticas > IVA**.
2. Haz clic en **Agregar regla** y selecciona **Cruce de linea (Line Crossing)**.
3. Dibuja **una sola linea recta** que atraviese el area de interes (ej. el pasillo de la puerta).
4. Configura las direcciones:
   - `A a B`: cuenta como **Entrada**.
   - `B a A`: cuenta como **Salida**.
   - `A y B`: cuenta ambas direcciones.
5. Asegurate de que la regla este **Habilitada** y guarda los cambios.

### Paso 4 — Habilitar Notificaciones ONVIF

Para que la camara envie los eventos en tiempo real al backend:

1. Ve a **Red > ONVIF**.
2. Habilita el protocolo ONVIF y crea un usuario con las mismas credenciales que pondras en `.env`.
3. Ve a **Evento > Reglas de evento** (Event Rules).
4. Asegurate de que la linea virtual este habilitada y tenga permiso de notificar eventos.

---

## Instalacion — Linux

### 1. Clonar o descargar el proyecto

```bash
git clone <url-del-repositorio> conteo_personas
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
nano backend/.env
```

### 4. Iniciar el sistema

```bash
chmod +x start.sh
./start.sh
```

Abre tu navegador en: **http://localhost:3001**

---

## Instalacion — Windows

### 1. Instalar Python

1. Descarga Python 3.11+ desde [python.org](https://www.python.org/downloads/).
2. Durante la instalacion, **marca la casilla "Add Python to PATH"**.
3. Verifica: `python --version`

### 2. Descargar el proyecto

Descarga y descomprime el ZIP del proyecto.

### 3. Configurar credenciales

```cmd
copy backend\.env.example backend\.env
```

Abre `backend\.env` con el Bloc de Notas y rellena tus datos.

### 4. Iniciar el sistema

Haz doble clic en `start.bat` desde el Explorador de Archivos.

El script realizara automaticamente:
- Crear el entorno virtual Python
- Instalar todas las dependencias
- Levantar el backend y el frontend en paralelo

Abre tu navegador en: **http://localhost:3001**

> Si aparece una advertencia de SmartScreen, haz clic en "Mas informacion" > "Ejecutar de todas formas".

---

## Configurar Credenciales (.env)

Edita el archivo `backend/.env` (nunca subas este archivo a git):

```dotenv
# Credenciales compartidas por todas las camaras
CAMERA_USER=admin
CAMERA_PASS=tu_contrasena

# Camara 0: una sola camara para entradas y salidas
CAMERA_0_IP=192.168.1.100
CAMERA_0_NAME=Entrada Principal
CAMERA_0_ROLE=both

# Alternativa: dos camaras para la misma puerta (una por sentido)
# CAMERA_0_ROLE=in_only
# CAMERA_0_GROUP=puerta_principal
# CAMERA_1_IP=192.168.1.101
# CAMERA_1_NAME=Salida Principal
# CAMERA_1_ROLE=out_only
# CAMERA_1_GROUP=puerta_principal

POLL_INTERVAL_SECONDS=3
DATABASE_URL=sqlite:///./conteo_personas.db

TIMEZONE=America/Lima
BUSINESS_HOUR_START=0
BUSINESS_HOUR_END=24
```

---

## Iniciar el Sistema

| Sistema | Comando |
|---------|---------|
| Linux / macOS | `./start.sh` |
| Windows | Doble clic en `start.bat` |

**Dashboard tiempo real:** http://localhost:3001/index.html
**Dashboard analitica:** http://localhost:3001/analytics.html
**Documentacion API:** http://localhost:8000/docs

---

## API Endpoints

Con el backend corriendo, accede a la documentacion interactiva en **http://localhost:8000/docs**.

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `GET` | `/api/cameras` | Lista las camaras configuradas |
| `GET` | `/api/stats/historical` | Historico de eventos (filtrable por `camera_id`, `group`, `limit`) |
| `GET` | `/api/export/excel` | Exporta datos a `.xlsx` (parametros: `camera_id`, `group`, `date_from`, `date_to`) |
| `POST` | `/api/import/excel` | Importa datos desde un `.xlsx` |
| `WS` | `/ws/live` | Stream WebSocket en tiempo real |
| `GET` | `/docs` | Swagger UI |

---

## Estructura del Proyecto

```
conteo_personas/
+-- start.sh                  <- Inicio rapido en Linux/macOS
+-- start.bat                 <- Inicio rapido en Windows
+-- .gitignore
+-- README.md
|
+-- backend/
|   +-- .env                  <- Credenciales (NO subir a git)
|   +-- .env.example          <- Plantilla de configuracion
|   +-- requirements.txt
|   +-- config.py             <- Variables de entorno tipadas (TIMEZONE, ROLE, GROUP...)
|   +-- database.py           <- Motor SQLAlchemy (SQLite / PostgreSQL)
|   +-- models.py             <- Tablas ORM (CountingEvent, Camera, HourlyStat)
|   +-- schemas.py            <- Validacion Pydantic
|   +-- sunapi.py             <- Cliente ONVIF (Zeep) para suscripcion de eventos
|   +-- poller.py             <- Demonio asincrono: event-driven + heartbeat + roles
|   +-- main.py               <- FastAPI: rutas REST, WebSocket, ciclo de vida
|   +-- services/
|       +-- excel_service.py  <- Generacion y parseo de archivos Excel (SRP)
|
+-- frontend/
    +-- index.html            <- Dashboard tiempo real
    +-- analytics.html        <- Dashboard de analitica historica
    +-- css/
    |   +-- style.css         <- Estilos base (variables, layout, componentes)
    |   +-- analytics.css     <- Estilos especificos del dashboard analitico
    +-- js/
        +-- app.js            <- Logica del dashboard tiempo real
        +-- analytics.js      <- Logica del dashboard analitico
```

---

## Solucion de Problemas

| Problema | Causa probable | Solucion |
|----------|---------------|----------|
| `Error de conexion con la camara X.X.X.X` | IP incorrecta o camara apagada | Haz `ping 192.168.1.100` desde tu equipo. Si falla, revisa la red. |
| El conteo se queda en 0 | Evento no asignado en ONVIF | Revisa "Event Rules" en la camara y asegurate de que la linea virtual este activa. |
| `python: command not found` (Linux) | Python 3 no instalado | Instala con `sudo apt install python3 python3-venv python3-pip` |
| `pip: No existe el fichero` | venv corrupto | Elimina la carpeta `venv/` y vuelve a ejecutar `start.sh` o `start.bat`. |
| `Address already in use` | El puerto ya esta en uso | Cambia el puerto del frontend en el script (`3001` a `3002`, etc.) |
| SmartScreen bloquea `start.bat` | Windows Defender | Haz clic derecho en `start.bat` > Propiedades > Desbloquear. |
| Dashboard muestra "Desconectado" | Backend no corriendo | Verifica que `main.py` este ejecutandose sin errores en su consola. |
| El Excel exportado esta vacio | Sin datos en el rango de fechas | Amplia el rango de fechas o verifica que haya actividad registrada en la BD. |
| Error al importar Excel | Columnas incorrectas | El archivo debe tener las columnas: `Fecha`, `Hora`, `Entradas`, `Salidas`. |
