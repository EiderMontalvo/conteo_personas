"""
app/repositories/event_repo.py
--------------------------------
Repository para CountingEvent y HourlyStat.
Único lugar que hace SQL sobre estas tablas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.counting import CountingEvent
from app.repositories.base import GenericRepository

logger = logging.getLogger(__name__)


class EventRepository(GenericRepository[CountingEvent]):
    """Acceso a datos para eventos de conteo."""

    def __init__(self) -> None:
        super().__init__(CountingEvent)

    def add_event(
        self,
        db: Session,
        *,
        camera_id: int,
        in_count: int,
        out_count: int,
        event_type: str,
        location_group: Optional[str],
        timestamp: datetime,
        people_inside: int = 0,
    ) -> CountingEvent:
        """Persiste un evento de conteo."""
        event = CountingEvent(
            camera_id=camera_id,
            in_count=in_count,
            out_count=out_count,
            event_type=event_type,
            location_group=location_group,
            timestamp=timestamp,
            people_inside=people_inside,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_historical(
        self,
        db: Session,
        *,
        camera_id: Optional[int] = None,
        group: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 500,
    ) -> List[CountingEvent]:
        """Histórico filtrable. Toda la lógica de filtrado en un solo lugar."""
        q = db.query(CountingEvent).order_by(CountingEvent.timestamp.desc())
        if camera_id is not None:
            q = q.filter(CountingEvent.camera_id == camera_id)
        if group is not None:
            q = q.filter(CountingEvent.location_group == group)
        if date_from is not None:
            q = q.filter(CountingEvent.timestamp >= date_from)
        if date_to is not None:
            q = q.filter(CountingEvent.timestamp < date_to)
        return q.limit(limit).all()

    def get_for_export(
        self,
        db: Session,
        *,
        camera_id: Optional[int] = None,
        group: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> List[CountingEvent]:
        """Todos los eventos en rango para exportar (sin limit)."""
        q = db.query(CountingEvent).order_by(CountingEvent.timestamp.asc())
        if camera_id is not None:
            q = q.filter(CountingEvent.camera_id == camera_id)
        if group is not None:
            q = q.filter(CountingEvent.location_group == group)
        if date_from is not None:
            q = q.filter(CountingEvent.timestamp >= date_from)
        if date_to is not None:
            q = q.filter(CountingEvent.timestamp < date_to)
        return q.all()


# Singleton para inyectar por dependencia
event_repo = EventRepository()
