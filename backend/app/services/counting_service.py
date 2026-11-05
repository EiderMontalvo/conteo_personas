"""Conteo de personas: aplica el rol de la cámara, persiste eventos y emite por WebSocket.

El estado del día vive en CameraState (sobrevive a reinicios) y se reinicia al cambiar
de día en la zona horaria configurada.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Optional

import pytz

from app.core.config import settings
from app.core.defaults import DEFAULT_CRITICAL_THRESHOLD, DEFAULT_WARNING_THRESHOLD
from app.repositories.camera_repo import camera_repo
from app.repositories.event_repo import event_repo
from app.websockets.connection_manager import ws_manager

logger = logging.getLogger(__name__)

_COUNTS_IN = ("both", "in_only", "space")
_COUNTS_OUT = ("both", "out_only", "space")


@dataclass
class _DayState:
    day: date
    total_in: int = 0
    total_out: int = 0
    inside: int = 0


class CountingService:
    """Sin actividad no hay broadcast; solo un hourly_heartbeat por hora en horario de negocio."""

    def __init__(self) -> None:
        self._tz = pytz.timezone(settings.timezone)
        self._states: Dict[int, _DayState] = {}
        self._last_heartbeat: Dict[int, datetime] = {}

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
        max_capacity: Optional[int] = None,
        now_utc: Optional[datetime] = None,
    ) -> None:
        eff_in = raw_in if camera_role in _COUNTS_IN else 0
        eff_out = raw_out if camera_role in _COUNTS_OUT else 0

        now_utc = now_utc or datetime.now(timezone.utc)
        now_local = now_utc.astimezone(self._tz)
        state = self._day_state(db, camera_id, now_local.date())

        if eff_in == 0 and eff_out == 0:
            self._maybe_heartbeat(db, camera_id, camera_name, camera_group, state, now_utc, now_local)
            return

        state.total_in += eff_in
        state.total_out += eff_out
        state.inside = max(0, state.inside + eff_in - eff_out)

        camera_repo.upsert_state(
            db,
            camera_id=camera_id,
            people_inside=state.inside,
            total_in=state.total_in,
            total_out=state.total_out,
            status=self._capacity_status(db, state.inside, max_capacity),
            last_update=now_utc,
        )
        event_repo.add_event(
            db,
            camera_id=camera_id,
            in_count=eff_in,
            out_count=eff_out,
            event_type="change_event",
            location_group=camera_group,
            timestamp=now_utc,
            people_inside=state.inside,
        )
        self._last_heartbeat[camera_id] = now_utc

        await ws_manager.broadcast({
            "type": "count_update",
            "payload": {
                "camera_id": camera_id,
                "camera_name": camera_name,
                "group": camera_group,
                "timestamp": now_utc.isoformat(),
                "in_count": eff_in,
                "out_count": eff_out,
                "accum_in": state.total_in,
                "accum_out": state.total_out,
                "people_inside": state.inside,
            },
        })

    def _day_state(self, db, camera_id: int, today: date) -> _DayState:
        state = self._states.get(camera_id)
        if state is None:
            state = self._load_state(db, camera_id, today)
            self._states[camera_id] = state
        if state.day != today:
            logger.info("Nuevo día para cámara %d: se reinician los totales.", camera_id)
            state = _DayState(day=today)
            self._states[camera_id] = state
        return state

    def _load_state(self, db, camera_id: int, today: date) -> _DayState:
        """Recupera el estado guardado si es de hoy (p. ej. tras reiniciar el servidor)."""
        row = camera_repo.get_state(db, camera_id)
        if row is None or row.last_update is None:
            return _DayState(day=today)
        updated = row.last_update
        if updated.tzinfo is None:  # SQLite devuelve datetimes naive (UTC)
            updated = updated.replace(tzinfo=timezone.utc)
        if updated.astimezone(self._tz).date() != today:
            return _DayState(day=today)
        return _DayState(
            day=today,
            total_in=row.total_in,
            total_out=row.total_out,
            inside=row.people_inside,
        )

    def reset_cache(self) -> None:
        """Olvida el estado en RAM (se recarga de BD en el próximo evento)."""
        self._states.clear()
        self._last_heartbeat.clear()

    def _maybe_heartbeat(self, db, camera_id, camera_name, camera_group, state, now_utc, now_local):
        """Un registro por hora sin actividad, dentro del horario de negocio."""
        last_hb = self._last_heartbeat.get(camera_id)
        due = last_hb is None or (now_utc - last_hb) >= timedelta(hours=1)
        if not (due and self._within_business_hours(now_local)):
            return
        event_repo.add_event(
            db,
            camera_id=camera_id,
            in_count=0,
            out_count=0,
            event_type="hourly_heartbeat",
            location_group=camera_group,
            timestamp=now_utc,
            people_inside=state.inside,
        )
        self._last_heartbeat[camera_id] = now_utc
        logger.info("Heartbeat guardado para '%s' a las %s", camera_name, now_local.strftime("%H:%M"))

    @staticmethod
    def _capacity_status(db, inside: int, max_capacity: Optional[int]) -> str:
        if not max_capacity:
            return "Normal"
        from app.repositories.settings_repo import settings_repo

        row = settings_repo.get_singleton(db)
        warn = row.warning_threshold or DEFAULT_WARNING_THRESHOLD
        crit = row.critical_threshold or DEFAULT_CRITICAL_THRESHOLD
        pct = inside * 100 / max_capacity
        if pct > 100:
            return "Excedido"
        if pct >= crit:
            return "Crítico"
        if pct >= warn:
            return "Advertencia"
        return "Normal"

    def _within_business_hours(self, now_local: datetime) -> bool:
        h = now_local.hour
        start = settings.business_hour_start
        end = settings.business_hour_end
        if start < end:
            return start <= h < end
        return h >= start or h < end  # Horario que cruza medianoche


counting_service = CountingService()
