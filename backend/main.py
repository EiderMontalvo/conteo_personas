"""
main.py
-------
Punto de entrada de la aplicación FastAPI.
Solo contiene declaración de rutas y ciclo de vida de la app.
La lógica de negocio reside en los módulos del paquete services/.
Principio SOLID: Single Responsibility + Dependency Inversion.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator, List, Optional

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import database
import models
import poller
from config import settings
from services.excel_service import build_excel, parse_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Crear tablas en la BD al arrancar (idempotente: no destruye datos existentes)
models.Base.metadata.create_all(bind=database.engine)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestiona el ciclo de vida de la aplicación."""
    logger.info("Arrancando sistema. Camaras configuradas: %d", len(settings.cameras))
    for cam in settings.cameras:
        logger.info(
            "  [%d] %s -> %s (rol: %s, grupo: %s)",
            cam.camera_id, cam.name, cam.ip, cam.role, cam.group or "—",
        )

    tasks = await poller.start_all_pollers(
        cameras=settings.cameras,
        interval=settings.poll_interval,
    )

    yield

    for task in tasks:
        task.cancel()
    logger.info("Todas las tareas de polling han sido canceladas.")


app = FastAPI(
    title="Conteo de personas API",
    description="Sistema de monitorizacion en tiempo real de conteo de personas.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# WebSocket — tiempo real
# ──────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """WebSocket de datos en tiempo real. El poller empuja mensajes aqui."""
    await websocket.accept()
    poller.active_connections.append(websocket)
    logger.info("Cliente WS conectado. Total activos: %d", len(poller.active_connections))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        poller.active_connections.remove(websocket)
        logger.info("Cliente WS desconectado. Total activos: %d", len(poller.active_connections))


# ──────────────────────────────────────────────
# REST — Camaras
# ──────────────────────────────────────────────

@app.get("/api/cameras", summary="Lista las camaras configuradas")
def get_cameras() -> List[dict]:
    """Devuelve metadatos de cada camara (sin credenciales)."""
    return [
        {
            "id":    c.camera_id,
            "name":  c.name,
            "ip":    c.ip,
            "role":  c.role,
            "group": c.group,
        }
        for c in settings.cameras
    ]


# ──────────────────────────────────────────────
# REST — Historico
# ──────────────────────────────────────────────

@app.get("/api/stats/historical", summary="Historico de eventos de conteo")
def get_historical(
    camera_id: Optional[int] = Query(None, description="ID de camara"),
    group: Optional[str]     = Query(None, description="Grupo logico de camaras"),
    limit: int               = Query(500,  description="Maximo de registros a devolver"),
    db: Session = Depends(database.get_db),
) -> dict:
    """
    Retorna eventos de conteo ordenados por fecha descendente.
    Filtrable por camara o por grupo. Los heartbeats de inactividad
    (event_type='hourly_heartbeat') se incluyen para preservar la continuidad temporal.
    """
    query = db.query(models.CountingEvent).order_by(
        models.CountingEvent.timestamp.desc()
    )
    if camera_id is not None:
        query = query.filter(models.CountingEvent.camera_id == camera_id)
    if group is not None:
        query = query.filter(models.CountingEvent.location_group == group)

    events = query.limit(limit).all()
    return {
        "total": len(events),
        "data": [
            {
                "id":             e.id,
                "camera_id":      e.camera_id,
                "location_group": e.location_group,
                "timestamp":      e.timestamp.isoformat(),
                "in_count":       e.in_count,
                "out_count":      e.out_count,
                "event_type":     e.event_type,
            }
            for e in events
        ],
    }


# ──────────────────────────────────────────────
# REST — Exportar Excel
# ──────────────────────────────────────────────

@app.get("/api/export/excel", summary="Exportar datos a Excel")
def export_excel(
    camera_id: Optional[int] = Query(None, description="ID de camara"),
    group: Optional[str]     = Query(None, description="Grupo logico"),
    date_from: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    date_to:   Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD (inclusive)"),
    db: Session = Depends(database.get_db),
):
    """
    Genera y descarga un archivo .xlsx con los datos sanitizados,
    agrupados por hora, con flujo neto y personas en local calculados.
    Los timestamps se convierten a la zona horaria configurada en TIMEZONE.
    """
    query = db.query(models.CountingEvent).order_by(models.CountingEvent.timestamp.asc())

    if camera_id is not None:
        query = query.filter(models.CountingEvent.camera_id == camera_id)
    if group is not None:
        query = query.filter(models.CountingEvent.location_group == group)
    if date_from:
        try:
            query = query.filter(
                models.CountingEvent.timestamp >= datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            )
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(
                models.CountingEvent.timestamp < (
                    datetime.strptime(date_to, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
                )
            )
        except ValueError:
            pass

    events    = query.all()
    cam_names = {c.camera_id: c.name for c in settings.cameras}

    stream = build_excel(
        events=events,
        cam_names=cam_names,
        tz_name=settings.timezone,
        date_from=date_from,
        date_to=date_to,
    )

    filename = f"conteo_{date_from or 'all'}_{date_to or 'all'}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ──────────────────────────────────────────────
# REST — Importar Excel
# ──────────────────────────────────────────────

@app.post("/api/import/excel", summary="Importar datos desde Excel")
async def import_excel(
    file: UploadFile = File(..., description="Archivo .xlsx con columnas: Fecha, Hora, Entradas, Salidas"),
    db: Session = Depends(database.get_db),
) -> dict:
    """
    Importa registros desde un archivo Excel.
    Columnas requeridas: Fecha (YYYY-MM-DD), Hora (HH:MM), Entradas, Salidas.
    Columnas opcionales: Camara, Grupo.
    Los datos importados se marcan con event_type='imported'.
    """
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        return {"ok": False, "error": "Solo se aceptan archivos .xlsx o .xlsm"}

    contents = await file.read()
    cam_name_to_id = {c.name.lower(): c.camera_id for c in settings.cameras}

    try:
        records, errors = parse_excel(
            file_bytes=contents,
            tz_name=settings.timezone,
            cam_name_to_id=cam_name_to_id,
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    for rec in records:
        db.add(models.CountingEvent(
            camera_id=rec["camera_id"],
            in_count=rec["in_count"],
            out_count=rec["out_count"],
            event_type="imported",
            location_group=rec["location_group"],
            timestamp=rec["timestamp"],
        ))
    db.commit()

    return {
        "ok":       True,
        "inserted": len(records),
        "errors":   errors[:20],
    }


# ──────────────────────────────────────────────
# REST — Ajustes y Configuración
# ──────────────────────────────────────────────
from schemas import CameraConfigUpdate, SystemSettingsUpdate

@app.get("/api/settings", summary="Obtener configuración general")
def get_settings(db: Session = Depends(database.get_db)):
    settings_db = db.query(models.SystemSettings).first()
    if not settings_db:
        settings_db = models.SystemSettings()
        db.add(settings_db)
        db.commit()
        db.refresh(settings_db)
    return settings_db

@app.put("/api/settings", summary="Actualizar configuración general")
def update_settings(data: SystemSettingsUpdate, db: Session = Depends(database.get_db)):
    settings_db = db.query(models.SystemSettings).first()
    if not settings_db:
        settings_db = models.SystemSettings()
        db.add(settings_db)
    
    update_data = data.model_dump(exclude_unset=True) if hasattr(data, 'model_dump') else data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings_db, key, value)
    
    db.commit()
    db.refresh(settings_db)
    return {"ok": True, "settings": settings_db}

@app.get("/api/cameras/config", summary="Lista configuración extendida de cámaras")
def get_cameras_config(db: Session = Depends(database.get_db)):
    for cam_conf in settings.cameras:
        c_db = db.query(models.Camera).filter(models.Camera.camera_id == cam_conf.camera_id).first()
        if not c_db:
            c_db = models.Camera(
                camera_id=cam_conf.camera_id,
                ip_address=cam_conf.ip,
                name=cam_conf.name,
                zone=cam_conf.group
            )
            db.add(c_db)
    db.commit()
    return db.query(models.Camera).all()

@app.put("/api/cameras/{cam_id}", summary="Actualizar configuración de cámara")
def update_camera(cam_id: int, data: CameraConfigUpdate, db: Session = Depends(database.get_db)):
    c_db = db.query(models.Camera).filter(models.Camera.id == cam_id).first()
    if not c_db:
        return {"ok": False, "error": "Cámara no encontrada"}
    
    update_data = data.model_dump(exclude_unset=True) if hasattr(data, 'model_dump') else data.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(c_db, key, value)
    
    db.commit()
    db.refresh(c_db)
    return {"ok": True, "camera": c_db}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
