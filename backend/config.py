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
from typing import List

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


@dataclass(frozen=True)
class AppConfig:
    """Configuración global de la aplicación."""
    database_url: str
    poll_interval: int
    cameras: List[CameraConfig]


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
        name = os.getenv(f"CAMERA_{index}_NAME", f"Cámara {index}")
        cameras.append(
            CameraConfig(
                camera_id=index,
                ip=ip,
                name=name,
                user=user,
                password=password,
            )
        )
        index += 1

    return cameras


def get_settings() -> AppConfig:
    """Factoría que construye y devuelve la configuración de la aplicación."""
    return AppConfig(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./conteo_personas.db"),
        poll_interval=int(os.getenv("POLL_INTERVAL_SECONDS", "3")),
        cameras=_build_camera_list(),
    )


# Instancia singleton para toda la app
settings: AppConfig = get_settings()
