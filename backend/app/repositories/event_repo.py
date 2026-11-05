from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.dates import local_date
from app.models.counting import CountingEvent
from app.repositories.base import GenericRepository

logger = logging.getLogger(__name__)


class EventRepository(GenericRepository[CountingEvent]):
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

    def add_many_imported(self, db: Session, records: list[dict]) -> Dict[str, int]:
        """
        Upsert de registros importados de Excel por (camera_id, timestamp) entre
        eventos 'imported'. El timestamp se trunca al segundo porque el parser y
        SQLite pueden diferir en microsegundos.
        """
        if not records:
            return {"inserted": 0, "updated": 0}

        def _ts_key(ts: datetime) -> str:
            """UTC naive truncado al segundo."""
            return ts.replace(tzinfo=None, microsecond=0).isoformat()

        timestamps = [r["timestamp"] for r in records]
        ts_min = min(timestamps)
        ts_max = max(timestamps)

        existing_events: List[CountingEvent] = (
            db.query(CountingEvent)
            .filter(
                CountingEvent.event_type == "imported",
                CountingEvent.timestamp >= ts_min,
                CountingEvent.timestamp <= ts_max,
            )
            .order_by(CountingEvent.id.asc())
            .all()
        )

        # Si ya hay duplicados en BD se conserva el más antiguo y se borra el resto.
        existing_index: Dict[Tuple, CountingEvent] = {}
        to_delete: List[CountingEvent] = []
        for e in existing_events:
            key = (e.camera_id, _ts_key(e.timestamp))
            if key in existing_index:
                to_delete.append(e)
            else:
                existing_index[key] = e

        for dup in to_delete:
            db.delete(dup)

        inserted = 0
        updated = 0
        for rec in records:
            key = (rec["camera_id"], _ts_key(rec["timestamp"]))
            if key in existing_index:
                event = existing_index[key]
                event.in_count = rec["in_count"]
                event.out_count = rec["out_count"]
                event.location_group = rec["location_group"]
                updated += 1
            else:
                db.add(CountingEvent(
                    camera_id=rec["camera_id"],
                    in_count=rec["in_count"],
                    out_count=rec["out_count"],
                    event_type="imported",
                    location_group=rec["location_group"],
                    timestamp=rec["timestamp"].replace(microsecond=0),
                ))
                inserted += 1

        db.commit()
        return {"inserted": inserted, "updated": updated, "deduped": len(to_delete)}

    def purge_imported_duplicates(self, db: Session) -> int:
        """
        Por cada (camera_id, timestamp al segundo) de los 'imported' conserva el
        id más bajo y borra el resto. Devuelve cuántos se eliminaron.
        """
        all_imported: List[CountingEvent] = (
            db.query(CountingEvent)
            .filter(CountingEvent.event_type == "imported")
            .order_by(CountingEvent.id.asc())
            .all()
        )

        seen: Dict[Tuple, int] = {}
        to_delete: List[CountingEvent] = []
        for e in all_imported:
            key = (e.camera_id, e.timestamp.replace(tzinfo=None, microsecond=0).isoformat())
            if key in seen:
                to_delete.append(e)
            else:
                seen[key] = e.id

        for dup in to_delete:
            db.delete(dup)

        db.commit()
        logger.info("purge_imported_duplicates: %d registros eliminados", len(to_delete))
        return len(to_delete)

    def get_date_range(self, db: Session) -> Dict[str, Optional[str]]:
        """Primera y última fecha con eventos, sin contar heartbeats."""
        result = db.query(
            func.min(CountingEvent.timestamp),
            func.max(CountingEvent.timestamp),
        ).filter(
            CountingEvent.event_type != "hourly_heartbeat"
        ).one()

        min_ts, max_ts = result
        return {
            "first_date": local_date(min_ts).isoformat() if min_ts else None,
            "last_date":  local_date(max_ts).isoformat() if max_ts else None,
        }

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
        """Como get_historical pero en orden ascendente y sin límite."""
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


event_repo = EventRepository()
