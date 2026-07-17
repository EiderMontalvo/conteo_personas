"""
app/schemas/camera.py
---------------------
Schemas Pydantic para el recurso Cámara.
Contrato entre el backend y el frontend — no cambiar sin versionar.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CameraOut(BaseModel):
    """Respuesta completa de una cámara (sin credenciales)."""
    id: int
    camera_id: int
    name: str
    ip_address: str
    role: str
    zone: Optional[str] = None
    max_capacity: int
    is_active: bool
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    operating_hours_start: str
    operating_hours_end: str
    # Estado en tiempo real (se une desde CameraState)
    people_inside: Optional[int] = None
    total_in: Optional[int] = None
    total_out: Optional[int] = None
    status: Optional[str] = None

    model_config = {"from_attributes": True}


class CameraCreate(BaseModel):
    """Payload para crear una cámara nueva desde el frontend."""
    name: str = Field(..., min_length=1, max_length=100, description="Nombre descriptivo")
    ip_address: str = Field(..., description="IP de la cámara en la red local")
    role: str = Field("both", description="both | in_only | out_only")
    zone: Optional[str] = Field(None, description="Grupo lógico (ej. 'puerta_norte')")
    max_capacity: int = Field(150, ge=1, description="Aforo máximo")
    location: Optional[str] = Field(None, description="Descripción de ubicación")
    operating_hours_start: str = Field("00:00", description="HH:MM")
    operating_hours_end: str = Field("23:59", description="HH:MM")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"both", "in_only", "out_only"}
        if v not in allowed:
            raise ValueError(f"role debe ser uno de: {allowed}")
        return v


class CameraUpdate(BaseModel):
    """Payload para actualizar una cámara existente (todos los campos opcionales)."""
    name: Optional[str] = None
    ip_address: Optional[str] = None
    role: Optional[str] = None
    zone: Optional[str] = None
    max_capacity: Optional[int] = None
    is_active: Optional[bool] = None
    location: Optional[str] = None
    operating_hours_start: Optional[str] = None
    operating_hours_end: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in {"both", "in_only", "out_only"}:
            raise ValueError("role debe ser: both | in_only | out_only")
        return v


class DiscoveredCamera(BaseModel):
    """Cámara encontrada durante el escaneo de red."""
    ip: str
    port: int = 80
    manufacturer: str = "Desconocido"
    model: str = "Desconocido"
    already_added: bool = False   # True si ya existe en BD
