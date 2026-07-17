# Sistema de Business Intelligence y Conteo de Personas

Sistema local para monitorizar en tiempo real el flujo de personas usando camaras Hanwha Wisenet XNO-6120R a traves del protocolo ONVIF. Incluye persistencia historica, exportacion a Excel y un dashboard web.

Compatible con Windows 10/11 y Linux (Debian/Ubuntu/Arch).

---

## Indice

1. [Arquitectura general](#arquitectura-general)
2. [Requisitos previos](#requisitos-previos)
3. [Instalacion](#instalacion)
4. [Configuracion inicial](#configuracion-inicial)
5. [Iniciar el sistema](#iniciar-el-sistema)
6. [Configuracion de la camara Hanwha](#configuracion-de-la-camara-hanwha)
7. [Agregar camaras desde el frontend](#agregar-camaras-desde-el-frontend)
8. [Estructura del proyecto](#estructura-del-proyecto)
9. [Solucion de problemas](#solucion-de-problemas)

---

## Arquitectura general

```
Camaras Wisenet --ONVIF PullPoint-->
                                    Backend Python (FastAPI)
                                    - Polling asincrono por camara
                                    - Persistencia event-driven (SQLite/PostgreSQL)
                                    - Gestion dinamica de camaras (sin reinicio)
                                    - WebSocket + REST API v1
                                         |
                          WebSocket (tiempo real) + REST
                                         |
                                    Frontend (React + Recharts)
                                    - Dashboard tiempo real
                                    - Dashboard de analitica historica
                                    - Ajustes: camaras, sistema, exportacion
```

### Estrategia de almacenamiento

El sistema usa una estrategia event-driven para minimizar el espacio en disco:

- `change_event`: se guarda unicamente cuando los conteos cambian (alguien cruza la linea).
- `hourly_heartbeat`: si no hay actividad durante 1 hora dentro del horario de negocio, se guarda un registro con ceros para preservar la continuidad temporal en los reportes.
- `imported`: registros cargados desde un archivo Excel externo.

---

## Requisitos previos

| Componente | Version minima | Notas |
|---|---|---|
| Python | 3.9 | Con opcion "Add to PATH" activada en Windows |
| Node.js | 18 | Para el frontend React |
| Camara Hanwha XNO-6120R | Firmware 2.x+ | Con analitica IVA configurada y ONVIF habilitado |
| Navegador | Chrome 90+ / Firefox 88+ | Para el dashboard |
| Red | LAN | El equipo debe tener acceso directo a las IPs de las camaras |

---

## Instalacion

### Windows

1. Descarga y descomprime el proyecto.
2. Asegurate de tener Python 3.9+ instalado con la opcion "Add Python to PATH" activada.
3. Asegurate de tener Node.js 18+ instalado.
4. Haz doble clic en `start.bat`.

El script crea automaticamente el entorno virtual Python, instala todas las dependencias del backend y del frontend, y levanta ambos servicios.

> Si Windows Defender muestra una advertencia de SmartScreen, haz clic en "Mas informacion" y luego en "Ejecutar de todas formas". Esto ocurre la primera vez porque el archivo `.bat` no tiene firma digital.

### Linux / macOS

```bash
git clone <url-del-repositorio> conteo_personas
cd conteo_personas
chmod +x start.sh
./start.sh
```

---

## Configuracion inicial

Al arrancar por primera vez, el sistema crea automaticamente los archivos de base de datos. Solo necesitas proporcionar las credenciales ONVIF de tus camaras.

Copia la plantilla de configuracion:

```
Windows:  copy backend\.env.example backend\.env
Linux:    cp backend/.env.example backend/.env
```

Edita `backend/.env` y rellena como minimo:

```dotenv
CAMERA_USER=admin
CAMERA_PASS=tu_contrasena
```

Las camaras se pueden agregar desde la interfaz web sin editar mas el archivo `.env`. El sistema mantiene el `.env` sincronizado automaticamente cuando se realizan cambios desde el frontend.

Para una referencia completa de todas las variables de configuracion, consulta [`backend/README.md`](backend/README.md).

---

## Iniciar el sistema

| Sistema operativo | Comando |
|---|---|
| Windows | Doble clic en `start.bat` |
| Linux / macOS | `./start.sh` |

Una vez iniciado:

| Servicio | URL |
|---|---|
| Dashboard principal | http://localhost:3001 |
| Ajustes y camaras | http://localhost:3001 (menu lateral) |
| Documentacion API (Swagger) | http://localhost:8000/docs |

---

## Configuracion de la camara Hanwha

Estas configuraciones se realizan una sola vez desde la interfaz web de la camara (`http://<ip-camara>`). El sistema no puede realizar estas configuraciones de forma remota.

### Paso 1 — Configurar la linea virtual IVA

1. Ir a **Configuracion > Analiticas > IVA**.
2. Hacer clic en **Agregar regla** y seleccionar **Cruce de linea (Line Crossing)**.
3. Dibujar una linea recta que atraviese el area de interes.
4. Configurar las direcciones: `A a B` como Entrada, `B a A` como Salida.
5. Verificar que la regla este **Habilitada** y guardar.

### Paso 2 — Habilitar ONVIF

1. Ir a **Red > ONVIF**.
2. Habilitar el protocolo ONVIF.
3. Crear un usuario con el mismo nombre y contrasena que se indicaran en el `.env` (`CAMERA_USER` / `CAMERA_PASS`).

### Paso 3 — Verificar reglas de evento

1. Ir a **Evento > Reglas de evento**.
2. Verificar que la linea virtual este habilitada para notificar eventos ONVIF.

---

## Agregar camaras desde el frontend

Una vez que las camaras tienen ONVIF habilitado, se pueden agregar sin tocar ningun archivo de configuracion:

1. Abrir el frontend en el navegador.
2. Ir a **Ajustes** en el menu lateral.
3. Hacer clic en **Escanear Red** en el panel "Descubrir Camaras en la Red".
4. El sistema busca automaticamente camaras ONVIF en la red local. Puede tardar hasta 15 segundos.
5. Hacer clic en **Agregar** junto a la camara deseada.
6. Completar el formulario: nombre, rol de conteo y aforo maximo.
7. Hacer clic en **Guardar y Conectar**.

El sistema arranca el polling de esa camara de forma inmediata y actualiza el `.env` como respaldo.

Para cambiar la IP de una camara existente, usar el icono de edicion en cada tarjeta de camara en Ajustes. El poller se reconecta automaticamente con la nueva IP sin necesidad de reiniciar el servidor.

---

## Estructura del proyecto

```
conteo_personas/
├── start.bat                     <- Inicio rapido en Windows
├── start.sh                      <- Inicio rapido en Linux/macOS
├── README.md                     <- Este archivo
│
├── backend/
│   ├── README.md                 <- Documentacion tecnica detallada del backend
│   ├── .env                      <- Credenciales (no subir a git)
│   ├── .env.example              <- Plantilla de configuracion
│   ├── requirements.txt          <- Dependencias Python
│   ├── main.py                   <- Punto de entrada FastAPI
│   ├── database.py               <- Motor SQLAlchemy
│   └── app/
│       ├── api/v1/               <- Routers REST (cameras, analytics, excel, settings)
│       ├── core/                 <- Configuracion y logging
│       ├── models/               <- Modelos ORM (tablas de base de datos)
│       ├── schemas/              <- Schemas Pydantic (contrato con el frontend)
│       ├── repositories/         <- Acceso a datos (unico lugar con SQL)
│       ├── services/             <- Logica de negocio
│       ├── integrations/onvif/   <- Cliente ONVIF, PollerPool, descubrimiento de red
│       └── websockets/           <- Gestor de conexiones WebSocket
│
└── frontend/
    ├── package.json
    ├── index.html
    └── src/
        ├── pages/
        │   ├── Dashboard.jsx     <- Tiempo real: contadores y estado de aforo
        │   ├── Analytics.jsx     <- Analitica historica y graficas
        │   ├── CapacityControl.jsx <- Control de aforo por camara
        │   └── Settings.jsx      <- Configuracion de camaras y sistema
        └── components/           <- Componentes reutilizables (Topbar, Sidebar...)
```

---

## Solucion de problemas

| Problema | Causa probable | Solucion |
|---|---|---|
| Error de conexion con la camara en los logs | IP incorrecta o ONVIF no habilitado | Verificar con `ping <ip>`. Revisar que ONVIF este habilitado en la interfaz web de la camara. |
| El conteo se queda en cero | Linea virtual IVA no configurada o sin eventos ONVIF | Revisar la configuracion IVA y las reglas de evento en la interfaz de la camara. |
| "Escanear Red" no encuentra camaras | Firewall bloquea UDP 3702 (WS-Discovery) | El sistema intentara el TCP scan automaticamente. Verificar que las camaras esten encendidas y accesibles desde el equipo. |
| SmartScreen bloquea `start.bat` | Windows Defender (primer uso) | Clic derecho en `start.bat` > Propiedades > Desbloquear. O hacer clic en "Mas informacion" > "Ejecutar de todas formas". |
| `python: command not found` en Linux | Python 3 no instalado o no en PATH | `sudo apt install python3 python3-venv python3-pip` |
| `Address already in use` | El puerto 8000 o 3001 esta ocupado | Cerrar la instancia anterior o cambiar el puerto en `start.bat` / `start.sh`. |
| Dashboard muestra "Desconectado" | Backend no esta corriendo | Verificar que `start.bat` o `start.sh` haya terminado de iniciar sin errores. |
| El Excel exportado esta vacio | Sin datos en el rango de fechas seleccionado | Ampliar el rango de fechas o verificar que haya actividad registrada. |
| Error al importar Excel | Columnas incorrectas | El archivo debe tener las columnas: `Fecha`, `Hora`, `Entradas`, `Salidas`. |
| `pip: no se encontro el fichero` | Entorno virtual corrupto | Eliminar la carpeta `venv/` y volver a ejecutar el script de inicio. |
