"""
app/api/v1/analytics.py
------------------------
Endpoints históricos y de estadísticas.
La lógica de filtrado vive en EventRepository, no aquí.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import database
from app.repositories.event_repo import event_repo
from app.repositories.camera_repo import camera_repo
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/stats", tags=["Analítica"])
logger = logging.getLogger(__name__)


def _db():
    yield from database.get_db()


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Convierte 'YYYY-MM-DD' a datetime UTC o None si el string es inválido."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@router.get(
    "/historical",
    response_model=ApiResponse[List[dict]],
    summary="Histórico de eventos de conteo",
    description=(
        "Retorna eventos de conteo ordenados por fecha descendente. "
        "Filtrable por cámara, grupo y rango de fechas."
    ),
)
def get_historical(
    camera_id: Optional[int] = Query(None, description="ID lógico de cámara"),
    group: Optional[str] = Query(None, description="Grupo lógico de cámaras"),
    date_from: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD (inclusive)"),
    limit: int = Query(500, ge=1, le=5000, description="Máximo de registros"),
    db: Session = Depends(_db),
):
    dt_from = _parse_date(date_from)
    dt_to = _parse_date(date_to)
    if dt_to:
        dt_to = dt_to + timedelta(days=1)  # inclusive

    events = event_repo.get_historical(
        db,
        camera_id=camera_id,
        group=group,
        date_from=dt_from,
        date_to=dt_to,
        limit=limit,
    )
    data = [
        {
            "id": e.id,
            "camera_id": e.camera_id,
            "location_group": e.location_group,
            "timestamp": e.timestamp.isoformat(),
            "in_count": e.in_count,
            "out_count": e.out_count,
            "people_inside": e.people_inside,
            "event_type": e.event_type,
        }
        for e in events
    ]
    return ApiResponse.success(data, total=len(data))


@router.get(
    "/summary",
    response_model=ApiResponse[List[dict]],
    summary="Resumen del día actual por cámara",
    description="Devuelve totales de entrada/salida del día en curso para cada cámara activa.",
)
def get_summary(db: Session = Depends(_db)):
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cameras = camera_repo.get_active(db)
    summary = []
    for cam in cameras:
        events = event_repo.get_historical(
            db,
            camera_id=cam.camera_id,
            date_from=today_start,
            limit=10_000,
        )
        total_in = sum(e.in_count for e in events)
        total_out = sum(e.out_count for e in events)
        state = camera_repo.get_state(db, cam.camera_id)
        summary.append({
            "camera_id": cam.camera_id,
            "camera_name": cam.name,
            "zone": cam.zone,
            "total_in_today": total_in,
            "total_out_today": total_out,
            "people_inside": state.people_inside if state else 0,
            "status": state.status if state else "Normal",
        })
    return ApiResponse.success(summary, total=len(summary))
