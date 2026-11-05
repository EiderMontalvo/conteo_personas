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
| Camara Hanwha XNO-6120R | Probado con firmware 1.40.02 | Con analitica IVA configurada y ONVIF habilitado |
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

Estas configuraciones se realizan una sola vez desde la interfaz web de la camara (`http://<ip-camara>`, menu de engranaje). El sistema no las cambia por si mismo.

### Paso 0 — Ubicacion de la camara

La precision del conteo depende sobre todo de donde esta la camara:

- **Recomendado:** encima de la puerta, mirando hacia abajo (cenital o muy inclinada). Cada persona que entra o sale atraviesa la linea de forma limpia y quien pasa por al lado no la toca.
- **A evitar:** la camara a baja altura mirando de frente a la puerta. Quien cruza se mueve "en profundidad" (hacia la camara o alejandose) y casi no se desplaza en la imagen; ademas, quien camina de lado al fondo hace oscilar su recuadro y genera **cruces falsos o duplicados**.
- Que nada tape el umbral de la puerta (escritorios, mostradores): es justo donde va la linea.

### Paso 1 — Darle una IP fija

Una camara nueva viene en **DHCP**. Si se conecta directo al equipo o a un switch PoE sin servidor DHCP, se queda **sin IP** y ni el *Wisenet IP Installer* ni el sistema la encuentran.

1. Dale una IP por DHCP (router o servidor DHCP de la red) o con el IP Installer.
2. En **Basic > IP & Port** cambia el tipo a **Manual (estatica)** con una IP de la misma red que el equipo, p. ej. `192.168.50.100/24` y gateway `192.168.50.1`. Si queda en DHCP sin servidor, la camara pierde la IP al vencer la concesion.
3. Al primer acceso la camara pide crear la contrasena de `admin`; esa es la que va en `CAMERA_USER` / `CAMERA_PASS`.

### Paso 2 — Configurar la linea virtual IVA

En **Analytics > IVA**, con **Enable IVA** marcado:

1. Pestana **Virtual line**: dibuja la linea **dentro del vano de la puerta**, sin que sus extremos toquen paredes, y donde las personas la atraviesen por completo (sobre el umbral). En **Categories** marca **Crossing** y en **Direction** elige **A↔B** (ambos sentidos).
2. Pestana **Common**: ajusta el **tamano de objeto**. Si el minimo es demasiado grande (p. ej. 684×879) la camara no detecta a nadie; algo como **Minimum 100×200** y **Maximum** casi toda la imagen funciona bien.
3. Marca **Overlay > Enable** mientras pruebas: en el video de la camara aparece un recuadro sobre cada persona detectada.
4. En **Event action settings** no hace falta activar FTP, E-mail ni Record: son acciones opcionales y no afectan al envio de eventos por ONVIF.
5. **Apply.**

El sistema cuenta como **entrada** el cruce hacia un lado (*left*) y como **salida** el contrario (*right*). Cruza una vez hacia afuera: si sube "Entradas", el sentido esta invertido respecto a tu puerta.

La linea configurada se dibuja **en amarillo sobre el video en vivo** del dashboard (se refresca cada minuto), para comprobar donde esta.

> **Solo un sentido:** si en la camara pones la linea solo en A→B o A←B, la camara ignora el otro sentido y el aforo ("personas dentro") deja de tener sentido. Para contar un solo sentido es mejor dejar la linea en A↔B y usar el **rol** de la camara en el sistema (`in_only` / `out_only`, ver [`backend/README.md`](backend/README.md)).

### Paso 3 — Habilitar ONVIF

1. Ir a **Network > ONVIF** (o equivalente) y verificar que el protocolo este habilitado.
2. El usuario y la contrasena son los del `.env` (`CAMERA_USER` / `CAMERA_PASS`).

### Paso 4 — Perfil de video para el monitoreo en vivo

El MJPEG por defecto de Hanwha es el **perfil de grabacion**, que la camara limita a 2-5 fps: el video del dashboard se ve entrecortado y atrasado.

1. En **Basic > Video profile** marca **Keep connection when profile properties are changed** (si no, la camara corta todos los videos abiertos cada vez que se edita un perfil).
2. **Add** un perfil nuevo, p. ej. `LIVE`: codec **MJPEG**, resolucion **800×448**, **8 fps**.
3. Pon su numero en `backend/.env`: `VIDEO_PROFILE=4` (el numero es su posicion en la lista: MJPEG=1, H.264=2, H.265=3, LIVE=4).

No pidas mas fps de los que la camara puede codificar: si recibe mas de los que entrega, los cuadros se encolan y el video se atrasa varios segundos. Medido en la XNO-6120R: 1280×720 solo sostiene ~6 fps; 800×448 ~10 fps; 640×360 ~15 fps. Deja un margen por debajo de esos valores.

El perfil **H.264 (Default)** lo usan el visor web de la camara y un NVR/VMS; el sistema no lo usa. Cierra el visor web de la camara mientras monitoreas: compite por el procesador con el perfil LIVE.

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
| El conteo se queda en cero | Linea virtual IVA no configurada, tamano minimo de objeto demasiado grande, o la linea no se atraviesa | Revisar Analytics > IVA (pestanas Virtual line y Common). Activar Overlay para ver si la camara detecta a la persona. |
| Cuenta de mas o cruces que no ocurrieron | Camara frontal a baja altura, linea a media altura o que toca las paredes | Ver [Paso 0](#paso-0--ubicacion-de-la-camara) y [Paso 2](#paso-2--configurar-la-linea-virtual-iva). Lo ideal es la camara sobre la puerta mirando hacia abajo. |
| Entradas y salidas invertidas | El sentido *left/right* de la linea es el contrario al de tu puerta | Redibujar la linea con los extremos al reves en la camara. |
| La camara no aparece en IP Installer ni responde a ping | Esta en DHCP y no hay servidor DHCP en ese cable | Conectarla a una red con DHCP, darle IP y pasarla a estatica ([Paso 1](#paso-1--darle-una-ip-fija)). |
| Video del dashboard atrasado o a saltos | Se usa el MJPEG de grabacion (2-5 fps) o el perfil pide mas fps de los que la camara codifica | Crear un perfil MJPEG propio con fps sostenibles y poner `VIDEO_PROFILE` ([Paso 4](#paso-4--perfil-de-video-para-el-monitoreo-en-vivo)). |
| El video se queda congelado | La camara corto el stream | El backend reconecta solo (si no llegan cuadros en 10 s o la camara corta). Marcar "Keep connection when profile properties are changed" en la camara. |
| "Escanear Red" no encuentra camaras | Firewall bloquea UDP 3702 (WS-Discovery) | El sistema intentara el TCP scan automaticamente. Verificar que las camaras esten encendidas y accesibles desde el equipo. |
| SmartScreen bloquea `start.bat` | Windows Defender (primer uso) | Clic derecho en `start.bat` > Propiedades > Desbloquear. O hacer clic en "Mas informacion" > "Ejecutar de todas formas". |
| `python: command not found` en Linux | Python 3 no instalado o no en PATH | `sudo apt install python3 python3-venv python3-pip` |
| `Address already in use` | El puerto 8000 o 3001 esta ocupado | Cerrar la instancia anterior o cambiar el puerto en `start.bat` / `start.sh`. |
| Dashboard muestra "Desconectado" | Backend no esta corriendo | Verificar que `start.bat` o `start.sh` haya terminado de iniciar sin errores. |
| El Excel exportado esta vacio | Sin datos en el rango de fechas seleccionado | Ampliar el rango de fechas o verificar que haya actividad registrada. |
| Error al importar Excel | Columnas incorrectas | El archivo debe tener las columnas: `Fecha`, `Hora`, `Entradas`, `Salidas`. |
| `pip: no se encontro el fichero` | Entorno virtual corrupto | Eliminar la carpeta `venv/` y volver a ejecutar el script de inicio. |
