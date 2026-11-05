"""Endpoints de histórico y estadísticas."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

import database
from app.core.dates import end_of_day_inclusive, local_today_start_utc, parse_date
from app.repositories.event_repo import event_repo
from app.repositories.camera_repo import camera_repo
from app.repositories.settings_repo import settings_repo
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/stats", tags=["Analítica"])
logger = logging.getLogger(__name__)


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
    limit: int = Query(500, ge=1, le=100_000, description="Máximo de registros"),
    db: Session = Depends(database.get_db),
):
    dt_from = parse_date(date_from)
    dt_to = end_of_day_inclusive(parse_date(date_to))  # inclusive

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
            "timestamp": e.timestamp.replace(tzinfo=timezone.utc).isoformat(),
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
def get_summary(db: Session = Depends(database.get_db)):
    today_start = local_today_start_utc()
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


@router.get(
    "/capacity",
    response_model=ApiResponse[List[dict]],
    summary="Estado de aforo por espacio (cámaras tipo space)",
    description=(
        "Devuelve el estado en tiempo real de todas las cámaras con role='space'. "
        "Incluye people_inside, max_capacity, porcentaje de ocupación y estado semafórico."
    ),
)
def get_capacity(db: Session = Depends(database.get_db)):
    """Datos del panel de Control de Aforo; solo cámaras con role='space'."""
    # get_singleton crea la fila con los DEFAULT_* si no existe.
    settings_row = settings_repo.get_singleton(db)
    warn_threshold = settings_row.warning_threshold
    crit_threshold = settings_row.critical_threshold

    cameras = camera_repo.get_active(db)
    space_cameras = [c for c in cameras if c.role == "space"]

    result = []
    for cam in space_cameras:
        state = camera_repo.get_state(db, cam.camera_id)
        people = state.people_inside if state else 0
        max_cap = cam.max_capacity or 1
        pct = round((people / max_cap) * 100)

        if pct >= crit_threshold:
            status = "Crítico"
        elif pct >= warn_threshold:
            status = "Advertencia"
        else:
            status = "Normal"

        result.append({
            "id": cam.id,
            "camera_id": cam.camera_id,
            "name": cam.name,
            "zone": cam.zone,
            "location": cam.location,
            "max_capacity": cam.max_capacity,
            "people_inside": people,
            "available": max(0, max_cap - people),
            "pct": pct,
            "status": status,
            "total_in": state.total_in if state else 0,
            "total_out": state.total_out if state else 0,
            "warning_threshold": warn_threshold,
            "critical_threshold": crit_threshold,
        })

    return ApiResponse.success(result, total=len(result))


@router.get(
    "/range",
    response_model=ApiResponse[dict],
    summary="Rango de fechas disponibles en el sistema",
    description=(
        "Retorna la fecha más antigua y más reciente registradas en la BD "
        "(excluyendo heartbeats). Útil para que el frontend sugiera el rango "
        "válido al filtrar por fechas."
    ),
)
def get_date_range(db: Session = Depends(database.get_db)):
    data = event_repo.get_date_range(db)
    return ApiResponse.success(data)
