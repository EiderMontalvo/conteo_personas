"""
config.py
---------
Módulo central de configuración. Carga variables desde el archivo .env
y expone objetos de configuración fuertemente tipados para toda la aplicación.
Principio SOLID: Single Responsibility (solo gestión de configuración).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Cargar .env desde la misma carpeta donde se encuentra este archivo
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


@dataclass(frozen=True)
class CameraConfig:
    """Configuración inmutable para una cámara individual."""
    camera_id: int
    ip: str
    name: str
    user: str
    password: str
    # Rol de la cámara respecto al conteo de personas:
    #   'both'     → cuenta entradas Y salidas (comportamiento por defecto)
    #   'in_only'  → solo cuenta entradas (ignora OUT de la cámara)
    #   'out_only' → solo cuenta salidas  (ignora IN de la cámara)
    role: str = "both"
    # Grupo lógico al que pertenece esta cámara.
    # Cámaras con el mismo grupo se consolidan en los reportes como un solo punto.
    # Ej.: CAMERA_0_GROUP=puerta_principal  CAMERA_1_GROUP=puerta_principal
    group: Optional[str] = None


@dataclass(frozen=True)
class AppConfig:
    """Configuración global de la aplicación."""
    database_url: str
    poll_interval: int
    cameras: List[CameraConfig]
    # Zona horaria local para exportaciones y reportes (ej. America/Lima)
    timezone: str
    # Rango horario en que el negocio opera (para heartbeats de inactividad)
    # Fuera de este rango no se generan heartbeats.
    # Rango: [business_hour_start, business_hour_end)
    # 0–24 = todo el día (por defecto)
    business_hour_start: int
    business_hour_end: int


def _build_camera_list() -> List[CameraConfig]:
    """
    Construye la lista de cámaras desde las variables de entorno.
    Soporta hasta N cámaras siguiendo el patrón CAMERA_{N}_IP / CAMERA_{N}_NAME.
    """
    user: str = os.getenv("CAMERA_USER", "admin")
    password: str = os.getenv("CAMERA_PASS", "")
    cameras: List[CameraConfig] = []

    index: int = 0
    while True:
        ip = os.getenv(f"CAMERA_{index}_IP")
        if ip is None:
            break  # No hay más cámaras definidas
        name  = os.getenv(f"CAMERA_{index}_NAME", f"Cámara {index}")
        role  = os.getenv(f"CAMERA_{index}_ROLE", "both").lower()
        group = os.getenv(f"CAMERA_{index}_GROUP", None)
        cameras.append(
            CameraConfig(
                camera_id=index,
                ip=ip,
                name=name,
                user=user,
                password=password,
                role=role,
                group=group,
            )
        )
        index += 1

    return cameras


def _clamp_hour(value: str, default: int) -> int:
    """Parsea un valor de hora (0-24) desde string, devolviendo el default si es inválido."""
    try:
        h = int(value)
        return max(0, min(24, h))
    except (ValueError, TypeError):
        return default


def get_settings() -> AppConfig:
    """Factoría que construye y devuelve la configuración de la aplicación."""
    return AppConfig(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./conteo_personas.db"),
        poll_interval=int(os.getenv("POLL_INTERVAL_SECONDS", "3")),
        cameras=_build_camera_list(),
        timezone=os.getenv("TIMEZONE", "America/Lima"),
        business_hour_start=_clamp_hour(os.getenv("BUSINESS_HOUR_START", "0"), 0),
        business_hour_end=_clamp_hour(os.getenv("BUSINESS_HOUR_END", "24"), 24),
    )


# Instancia singleton para toda la app
settings: AppConfig = get_settings()
