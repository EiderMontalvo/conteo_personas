"""Endpoints de exportación e importación de Excel (la lógica vive en excel_service)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

import database
from app.core.config import settings
from app.core.dates import end_of_day_inclusive, parse_date
from app.repositories.event_repo import event_repo
from app.repositories.camera_repo import camera_repo
from app.schemas.common import ApiResponse
from app.services.excel_service import build_excel, parse_excel

router = APIRouter(prefix="/excel", tags=["Excel"])
logger = logging.getLogger(__name__)


@router.get(
    "/export",
    summary="Exportar datos a Excel",
    description="Genera y descarga un archivo .xlsx con los conteos en el rango de fechas indicado.",
    responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}},
)
def export_excel(
    camera_id: Optional[int] = Query(None, description="ID lógico de cámara"),
    group: Optional[str] = Query(None, description="Grupo lógico"),
    date_from: Optional[str] = Query(None, description="Fecha inicio YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Fecha fin YYYY-MM-DD (inclusive)"),
    db: Session = Depends(database.get_db),
):
    dt_from = parse_date(date_from)
    dt_to = end_of_day_inclusive(parse_date(date_to))  # inclusive

    events = event_repo.get_for_export(
        db,
        camera_id=camera_id,
        group=group,
        date_from=dt_from,
        date_to=dt_to,
    )
    cam_names = {c.camera_id: c.name for c in camera_repo.get_all(db, limit=1000)}

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


@router.post(
    "/import",
    response_model=ApiResponse[dict],
    summary="Importar datos desde Excel",
    description="Importa registros desde un .xlsx. Columnas requeridas: Fecha, Hora, Entradas, Salidas.",
)
async def import_excel(
    file: UploadFile = File(..., description="Archivo .xlsx"),
    db: Session = Depends(database.get_db),
):
    if not (file.filename or "").lower().endswith((".xlsx", ".xlsm")):
        return ApiResponse.fail("Solo se aceptan archivos .xlsx o .xlsm")

    contents = await file.read()
    cameras = camera_repo.get_all(db, limit=1000)
    cam_name_to_id = {c.name.lower(): c.camera_id for c in cameras}

    try:
        records, errors = parse_excel(
            file_bytes=contents,
            tz_name=settings.timezone,
            cam_name_to_id=cam_name_to_id,
        )
    except ValueError as exc:
        return ApiResponse.fail(str(exc))

    result = event_repo.add_many_imported(db, records)

    return ApiResponse.success({
        "inserted": result["inserted"],
        "updated":  result["updated"],
        "errors":   errors[:20],
    })


@router.post(
    "/purge-duplicates",
    response_model=ApiResponse[dict],
    summary="Eliminar duplicados de registros importados",
    description=(
        "Limpia registros 'imported' duplicados en la BD (mismo camera_id y "
        "timestamp al segundo). Conserva el más antiguo y elimina el resto. "
        "Usar una sola vez para sanear datos previos al sistema de upsert."
    ),
)
def purge_duplicates(db: Session = Depends(database.get_db)):
    deleted = event_repo.purge_imported_duplicates(db)
    return ApiResponse.success({"deleted": deleted})

