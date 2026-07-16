"""
poller.py
---------
Servicio de sondeo en segundo plano (background task).
Crea una corutina asyncio por cada cámara configurada y hace polling
sin bloquear el event loop ni saturar la CPU de la cámara.

Estrategia de persistencia event-driven:
  - Solo se guarda en BD cuando hay un cambio real en los conteos (change_event).
  - Si no hay actividad durante 1 hora dentro del horario de negocio, se guarda
    un registro de heartbeat (hourly_heartbeat) con in=0, out=0 para preservar
    la continuidad temporal en los reportes.
  - Cámaras con rol 'in_only' solo registran entradas.
  - Cámaras con rol 'out_only' solo registran salidas.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple

from fastapi import WebSocket

import models
import database
from config import CameraConfig, settings
from sunapi import SunAPIClient

logger = logging.getLogger(__name__)

# Registro de conexiones WebSocket activas
active_connections: List[WebSocket] = []

# Estado en RAM por cámara: (in_count, out_count) del último evento persistido
_last_counts: Dict[int, Tuple[int, int]] = {}

# Timestamp del último heartbeat guardado por cámara
_last_heartbeat: Dict[int, datetime] = {}

# Contadores acumulados en RAM por cámara (reset al reiniciar el servidor)
_accum_counts: Dict[int, Tuple[int, int]] = {}


async def broadcast_ws(message: dict) -> None:
    """Envía un mensaje JSON a todos los clientes WebSocket conectados."""
    dead: List[WebSocket] = []
    for ws in active_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in active_connections:
            active_connections.remove(ws)


def _within_business_hours(now_local: datetime) -> bool:
    """Retorna True si la hora actual está dentro del horario de negocio configurado."""
    h = now_local.hour
    start = settings.business_hour_start
    end = settings.business_hour_end
    if start < end:
        return start <= h < end
    # Horario que cruza medianoche (ej. 20-4)
    return h >= start or h < end


async def poll_camera(camera: CameraConfig, interval: int) -> None:
    """
    Corutina de polling para UNA cámara.
    Aplica lógica event-driven y respeta el rol de la cámara.
    """
    import pytz

    client = SunAPIClient(camera)
    tz = pytz.timezone(settings.timezone)

    logger.info(
        "Iniciando polling para '%s' (%s) cada %ds.",
        camera.name, camera.ip, interval
    )

    while True:
        try:
            data = await client.get_realtime_count()

            if data is not None:
                raw_in  = data.in_count
                raw_out = data.out_count

                # Aplicar rol de cámara
                effective_in  = raw_in  if camera.role in ("both", "in_only")  else 0
                effective_out = raw_out if camera.role in ("both", "out_only") else 0

                # Si el rol es solo salidas, ignorar el delta de entradas y viceversa
                if camera.role == "in_only":
                    effective_out = 0
                elif camera.role == "out_only":
                    effective_in = 0

                now_utc   = datetime.now(timezone.utc)
                now_local = now_utc.astimezone(tz)

                # Actualizar acumulados en RAM
                prev_accum = _accum_counts.get(camera.camera_id, (0, 0))
                accum_in  = prev_accum[0] + effective_in
                accum_out = prev_accum[1] + effective_out
                _accum_counts[camera.camera_id] = (accum_in, accum_out)

                # Broadcast en tiempo real (siempre, con los valores efectivos)
                if effective_in > 0 or effective_out > 0:
                    await broadcast_ws({
                        "camera_id":   camera.camera_id,
                        "camera_name": camera.name,
                        "group":       camera.group,
                        "timestamp":   now_utc.isoformat(),
                        "in_count":    effective_in,
                        "out_count":   effective_out,
                    })

                # --- Persistencia event-driven ---
                last = _last_counts.get(camera.camera_id, (0, 0))
                has_change = (effective_in > 0 or effective_out > 0)

                if has_change:
                    # Guardar solo si hubo actividad real
                    _persist_event(
                        camera_id=camera.camera_id,
                        in_count=effective_in,
                        out_count=effective_out,
                        event_type="change_event",
                        group=camera.group,
                        timestamp=now_utc,
                    )
                    _last_counts[camera.camera_id] = (accum_in, accum_out)
                    _last_heartbeat[camera.camera_id] = now_utc
                else:
                    # Sin actividad: guardar heartbeat si pasó 1 hora y estamos en horario de negocio
                    last_hb = _last_heartbeat.get(camera.camera_id)
                    should_heartbeat = (
                        last_hb is None or (now_utc - last_hb) >= timedelta(hours=1)
                    ) and _within_business_hours(now_local)

                    if should_heartbeat:
                        _persist_event(
                            camera_id=camera.camera_id,
                            in_count=0,
                            out_count=0,
                            event_type="hourly_heartbeat",
                            group=camera.group,
                            timestamp=now_utc,
                        )
                        _last_heartbeat[camera.camera_id] = now_utc
                        logger.info(
                            "Heartbeat de inactividad guardado para '%s' a las %s",
                            camera.name, now_local.strftime("%H:%M")
                        )

        except asyncio.CancelledError:
            logger.info("Polling cancelado para cámara '%s'.", camera.name)
            return
        except Exception as exc:
            logger.exception("Error inesperado en poller (cámara %s): %s", camera.ip, exc)

        await asyncio.sleep(interval)


def _persist_event(
    camera_id: int,
    in_count: int,
    out_count: int,
    event_type: str,
    group: Optional[str],
    timestamp: datetime,
) -> None:
    """Guarda un evento en la base de datos de forma síncrona."""
    db = database.SessionLocal()
    try:
        event = models.CountingEvent(
            camera_id=camera_id,
            in_count=in_count,
            out_count=out_count,
            event_type=event_type,
            location_group=group,
            timestamp=timestamp,
        )
        db.add(event)
        db.commit()
    except Exception as db_exc:
        logger.error("Error escribiendo en BD (cámara %d): %s", camera_id, db_exc)
        db.rollback()
    finally:
        db.close()


async def start_all_pollers(cameras: List[CameraConfig], interval: int) -> List[asyncio.Task]:  # type: ignore[type-arg]
    """Lanza una tarea de polling independiente por cada cámara."""
    tasks = [
        asyncio.create_task(poll_camera(camera, interval), name=f"poller-cam-{camera.camera_id}")
        for camera in cameras
    ]
    logger.info("Lanzadas %d tareas de polling.", len(tasks))
    return tasks
