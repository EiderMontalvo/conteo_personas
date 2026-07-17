"""
app/core/config.py
------------------
Configuración central vía pydantic-settings.
Solo lee variables genéricas del .env; las IPs de cámaras viven en la BD.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Base de datos ──────────────────────────────────────────────
    database_url: str = "sqlite:///./conteo_personas.db"

    # ── Credenciales ONVIF compartidas por todas las cámaras ───────
    camera_user: str = "admin"
    camera_pass: str = ""

    # ── Polling ────────────────────────────────────────────────────
    poll_interval: int = 3

    # ── Zona horaria y horario de negocio ──────────────────────────
    timezone: str = "America/Lima"
    business_hour_start: int = 0
    business_hour_end: int = 24

    # ── CORS ───────────────────────────────────────────────────────
    cors_origins: List[str] = [
        "http://localhost:3001",
        "http://localhost:5173",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora CAMERA_{n}_IP etc. que ya no usamos aquí
    )


# Singleton para toda la aplicación
settings = Settings()
