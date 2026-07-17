"""
app/api/v1/settings.py
------------------------
Configuración del sistema (umbrales, zona horaria, intervalos).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import database
from app.models.counting import SystemSettings
from app.schemas.common import ApiResponse
from app.schemas.settings import SystemSettingsOut, SystemSettingsUpdate

router = APIRouter(prefix="/settings", tags=["Configuración"])
logger = logging.getLogger(__name__)


def _db():
    yield from database.get_db()


def _get_or_create_settings(db: Session) -> SystemSettings:
    s = db.query(SystemSettings).first()
    if s is None:
        s = SystemSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


@router.get(
    "",
    response_model=ApiResponse[SystemSettingsOut],
    summary="Obtener configuración del sistema",
)
def get_settings(db: Session = Depends(_db)):
    s = _get_or_create_settings(db)
    return ApiResponse.success(SystemSettingsOut.model_validate(s))


@router.put(
    "",
    response_model=ApiResponse[SystemSettingsOut],
    summary="Actualizar configuración del sistema",
)
def update_settings(data: SystemSettingsUpdate, db: Session = Depends(_db)):
    s = _get_or_create_settings(db)
    update_dict = data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        if hasattr(s, key):
            setattr(s, key, value)
    db.commit()
    db.refresh(s)
    return ApiResponse.success(SystemSettingsOut.model_validate(s))
