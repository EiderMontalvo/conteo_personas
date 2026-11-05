"""Configuración vía pydantic-settings: solo variables genéricas del .env (las IPs de cámaras viven en la BD)."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./conteo_personas.db"

    # Credenciales ONVIF compartidas por todas las cámaras.
    camera_user: str = "admin"
    camera_pass: str = ""

    # El .env usa POLL_INTERVAL_SECONDS (también se acepta POLL_INTERVAL).
    # Es el tiempo máximo que la cámara retiene cada PullMessages (long-poll).
    poll_interval: int = Field(
        3, ge=1, validation_alias=AliasChoices("POLL_INTERVAL_SECONDS", "POLL_INTERVAL")
    )

    onvif_port: int = 80
    # Timeout HTTP (s): sin él, una cámara apagada bloquea cada intento ~2 min.
    onvif_timeout: int = Field(8, ge=1)
    # Vida de la suscripción PullPoint en la cámara; se renueva a la mitad.
    onvif_subscription_ttl: int = Field(120, ge=30)
    # Desactivado: algunas cámaras cancelan TODAS las suscripciones (también
    # las de un NVR) al recibir Unsubscribe.
    onvif_unsubscribe: bool = False
    # Backoff de reconexión: 2s, 4s, 8s… hasta este máximo.
    reconnect_max_delay: int = Field(60, ge=2)
    # Perfil de video SUNAPI para el MJPEG en vivo. Vacío = el MJPEG por defecto,
    # que en Hanwha suele ser el perfil de grabación (limitado a 2-5 fps).
    video_profile: Optional[int] = Field(None, ge=1)

    # True = no se conecta a cámaras; genera cruces simulados.
    demo_mode: bool = False

    timezone: str = "America/Lima"
    business_hour_start: int = 0
    business_hour_end: int = 24

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


settings = Settings()
