"""Schemas de la configuración del sistema."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SystemSettingsOut(BaseModel):
    id: int
    update_interval: int
    heartbeat_interval: int
    timezone: str
    date_format: str
    time_format: str
    warning_threshold: int
    critical_threshold: int

    model_config = {"from_attributes": True}


class SystemSettingsUpdate(BaseModel):
    update_interval: Optional[int] = Field(None, ge=1, description="Segundos entre actualizaciones")
    heartbeat_interval: Optional[int] = Field(None, ge=60, description="Segundos entre heartbeats")
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None
    warning_threshold: Optional[int] = Field(None, ge=1, le=100)
    critical_threshold: Optional[int] = Field(None, ge=1, le=200)
