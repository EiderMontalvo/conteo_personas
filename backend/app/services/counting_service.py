"""
app/services/counting_service.py
----------------------------------
Lógica de negocio para el conteo de personas.
Extrae toda la lógica de roles, heartbeat y persistencia que antes estaba en poller.py.

Principio DRY: un único lugar decide si se guarda change_event o heartbeat;
nadie más repite esta lógica.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import pytz

from app.core.config import settings
from app.repositories.event_repo import event_repo
from app.websockets.connection_manager import ws_manager

logger = logging.getLogger(__name__)

# ── Estado en RAM (sobrevive reinicios de pollers individuales, no del servidor) ──
_last_counts: Dict[int, Tuple[int, int]] = {}    # camera_id → (in, out)
_last_heartbeat: Dict[int, datetime] = {}         # camera_id → último heartbeat UTC
_accum_counts: Dict[int, Tuple[int, int]] = {}    # camera_id → acumulado de sesión


class CountingService:
    """
    Procesa un evento de conteo crudo:
      1. Aplica el rol de la cámara (both / in_only / out_only).
      2. Actualiza acumulados en RAM.
      3. Hace broadcast WebSocket si hubo actividad.
      4. Persiste en BD (change_event o hourly_heartbeat).
    """

    def __init__(self) -> None:
        self._tz = pytz.timezone(settings.timezone)

    async def process(
        self,
        *,
        camera_id: int,
        camera_name: str,
        camera_role: str,
        camera_group: Optional[str],
        raw_in: int,
        raw_out: int,
        db,
    ) -> None:
        """
        Punto de entrada: recibe los conteos crudos de la cámara y los procesa.
        `db` es una sesión SQLAlchemy abierta por el poller (no por FastAPI).
        """
        # 1. Aplicar rol
        eff_in = raw_in if camera_role in ("both", "in_only") else 0
        eff_out = raw_out if camera_role in ("both", "out_only") else 0

        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(self._tz)

        # 2. Actualizar acumulados en RAM
        prev = _accum_counts.get(camera_id, (0, 0))
        accum_in = prev[0] + eff_in
        accum_out = prev[1] + eff_out
        _accum_counts[camera_id] = (accum_in, accum_out)

        # 3. Broadcast WebSocket (solo si hubo actividad)
        if eff_in > 0 or eff_out > 0:
            await ws_manager.broadcast({
                "type": "count_update",
                "payload": {
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "group": camera_group,
                    "timestamp": now_utc.isoformat(),
                    "in_count": eff_in,
                    "out_count": eff_out,
                    "accum_in": accum_in,
                    "accum_out": accum_out,
                },
            })

        # 4. Persistencia event-driven
        if eff_in > 0 or eff_out > 0:
            event_repo.add_event(
                db,
                camera_id=camera_id,
                in_count=eff_in,
                out_count=eff_out,
                event_type="change_event",
                location_group=camera_group,
                timestamp=now_utc,
            )
            _last_counts[camera_id] = (accum_in, accum_out)
            _last_heartbeat[camera_id] = now_utc
        else:
            # Sin actividad: guardar heartbeat si pasó 1 hora y estamos en horario de negocio
            last_hb = _last_heartbeat.get(camera_id)
            should_hb = (
                last_hb is None or (now_utc - last_hb) >= timedelta(hours=1)
            ) and self._within_business_hours(now_local)

            if should_hb:
                event_repo.add_event(
                    db,
                    camera_id=camera_id,
                    in_count=0,
                    out_count=0,
                    event_type="hourly_heartbeat",
                    location_group=camera_group,
                    timestamp=now_utc,
                )
                _last_heartbeat[camera_id] = now_utc
                logger.info(
                    "Heartbeat guardado para '%s' a las %s",
                    camera_name, now_local.strftime("%H:%M"),
                )

    def _within_business_hours(self, now_local: datetime) -> bool:
        """Retorna True si la hora actual cae dentro del horario de negocio."""
        h = now_local.hour
        start = settings.business_hour_start
        end = settings.business_hour_end
        if start < end:
            return start <= h < end
        return h >= start or h < end  # Horario que cruza medianoche


# Singleton compartido
counting_service = CountingService()
