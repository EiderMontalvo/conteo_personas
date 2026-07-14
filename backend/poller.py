"""
poller.py
---------
Servicio de sondeo en segundo plano (background task).
Crea una corutina asyncio por cada cámara configurada y hace polling
sin bloquear el event loop ni saturar la CPU de la cámara.
Principio SOLID: Open/Closed (añadir más cámaras no requiere modificar este módulo).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict

from fastapi import WebSocket

import models
import database
from config import CameraConfig
from sunapi import SunAPIClient

logger = logging.getLogger(__name__)

#Registro de conexiones WebSocket activas
# Permite broadcast selectivo o global.
active_connections: List[WebSocket] = []


async def broadcast_ws(message: dict) -> None:
    """Envía un mensaje JSON a todos los clientes WebSocket conectados."""
    dead: List[WebSocket] = []
    for ws in active_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    #Limpiar conexiones caídas
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)


async def poll_camera(camera: CameraConfig, interval: int) -> None:
    """
    Corutina de polling para UNA cámara.
    Persiste cada lectura en la BD y hace broadcast por WebSocket.
    """
    client = SunAPIClient(camera)
    logger.info(
        "Iniciando polling para '%s' (%s) cada %ds.",
        camera.name, camera.ip, interval
    )

    while True:
        try:
            data = await client.get_realtime_count()

            if data is not None:
                now = datetime.now(timezone.utc)

                #Broadcast en tiempo real a todos los clientes WS
                await broadcast_ws({
                    "camera_id": camera.camera_id,
                    "camera_name": camera.name,
                    "timestamp": now.isoformat(),
                    "in_count": data.in_count,
                    "out_count": data.out_count,
                })

                #Persistencia en base de datos
                db = database.SessionLocal()
                try:
                    event = models.CountingEvent(
                        camera_id=camera.camera_id,
                        in_count=data.in_count,
                        out_count=data.out_count,
                        event_type="real_time",
                        timestamp=now,
                    )
                    db.add(event)
                    db.commit()
                except Exception as db_exc:
                    logger.error("Error escribiendo en BD (cámara %s): %s", camera.ip, db_exc)
                    db.rollback()
                finally:
                    db.close()

        except asyncio.CancelledError:
            logger.info("Polling cancelado para cámara '%s'.", camera.name)
            return
        except Exception as exc:
            logger.exception("Error inesperado en poller (cámara %s): %s", camera.ip, exc)

        await asyncio.sleep(interval)


async def start_all_pollers(cameras: List[CameraConfig], interval: int) -> List[asyncio.Task]:  # type: ignore[type-arg]
    """Lanza una tarea de polling independiente por cada cámara."""
    tasks = [
        asyncio.create_task(poll_camera(camera, interval), name=f"poller-cam-{camera.camera_id}")
        for camera in cameras
    ]
    logger.info("Lanzadas %d tareas de polling.", len(tasks))
    return tasks
