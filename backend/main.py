"""
main.py
-------
Punto de entrada de la aplicación FastAPI.
Principio SOLID: Dependency Inversion (el servidor depende de abstracciones, no de implementaciones concretas).
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, List

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import database
import models
import poller
from config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

#Crear tablas en la BD al arrancar (idempotente: no destruye datos existentes)
models.Base.metadata.create_all(bind=database.engine)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gestiona el ciclo de vida de la aplicación."""
    logger.info(
        "Arrancando sistema. Cámaras configuradas: %d",
        len(settings.cameras),
    )
    for cam in settings.cameras:
        logger.info("  [%d] %s -> %s", cam.camera_id, cam.name, cam.ip)

    #Lanzar un poller por cada cámara
    tasks = await poller.start_all_pollers(
        cameras=settings.cameras,
        interval=settings.poll_interval,
    )

    yield

    #Cancelar todas las tareas al apagar
    for task in tasks:
        task.cancel()
    logger.info("Todas las tareas de polling han sido canceladas.")


app = FastAPI(
    title="BI People Counting API",
    description="Sistema de monitorización en tiempo real de conteo de personas.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#Endpoints

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """WebSocket de datos en tiempo real. El poller empujará mensajes aquí."""
    await websocket.accept()
    poller.active_connections.append(websocket)
    logger.info("Cliente WS conectado. Total activos: %d", len(poller.active_connections))
    try:
        while True:
            # Mantener viva la conexión; el poller empujará los datos
            await websocket.receive_text()
    except WebSocketDisconnect:
        poller.active_connections.remove(websocket)
        logger.info("Cliente WS desconectado. Total activos: %d", len(poller.active_connections))


@app.get("/api/cameras")
def get_cameras() -> List[dict]:
    """Lista las cámaras configuradas (sin contraseñas)."""
    return [
        {"id": c.camera_id, "name": c.name, "ip": c.ip}
        for c in settings.cameras
    ]


@app.get("/api/stats/historical")
def get_historical(
    camera_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(database.get_db),
) -> dict:
    """
    Retorna eventos históricos de conteo.
    Filtrable por camera_id. Preparado para consultas de ML.
    """
    query = db.query(models.CountingEvent).order_by(
        models.CountingEvent.timestamp.desc()
    )
    if camera_id is not None:
        query = query.filter(models.CountingEvent.camera_id == camera_id)

    events = query.limit(limit).all()
    return {
        "total": len(events),
        "data": [
            {
                "id": e.id,
                "camera_id": e.camera_id,
                "timestamp": e.timestamp.isoformat(),
                "in_count": e.in_count,
                "out_count": e.out_count,
                "event_type": e.event_type,
            }
            for e in events
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
