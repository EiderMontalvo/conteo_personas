"""Configuración del sistema (umbrales, zona horaria, intervalos)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import database
from app.repositories.settings_repo import settings_repo
from app.schemas.common import ApiResponse
from app.schemas.settings import SystemSettingsOut, SystemSettingsUpdate

router = APIRouter(prefix="/settings", tags=["Configuración"])
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=ApiResponse[SystemSettingsOut],
    summary="Obtener configuración del sistema",
)
def get_settings(db: Session = Depends(database.get_db)):
    s = settings_repo.get_singleton(db)
    return ApiResponse.success(SystemSettingsOut.model_validate(s))


@router.put(
    "",
    response_model=ApiResponse[SystemSettingsOut],
    summary="Actualizar configuración del sistema",
)
def update_settings(data: SystemSettingsUpdate, db: Session = Depends(database.get_db)):
    s = settings_repo.update_singleton(db, data.model_dump(exclude_unset=True))
    return ApiResponse.success(SystemSettingsOut.model_validate(s))
