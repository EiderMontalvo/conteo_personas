"""
app/models/counting.py
----------------------
Modelos ORM SQLAlchemy para el sistema de conteo de personas.
Única fuente de verdad para el esquema de la base de datos.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Camera(Base):
    """
    Representa una cámara física en el sistema.
    Fuente de verdad para la configuración de polling:
    el PollerPool lee de esta tabla, no del .env.
    """
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    # Índice lógico (0, 1, 2...) — mapea a CAMERA_{n}_* en el .env
    camera_id = Column(Integer, unique=True, index=True)
    ip_address = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # ── Conteo y rol ──────────────────────────────────────────────
    # Valores: both | in_only | out_only
    role = Column(String, default="both", nullable=False)
    # Grupo lógico: cámaras con el mismo grupo se consolidan en reportes
    zone = Column(String, nullable=True)
    max_capacity = Column(Integer, default=150, nullable=False)

    # ── Horario operativo ─────────────────────────────────────────
    operating_hours_start = Column(String, default="00:00", nullable=False)
    operating_hours_end = Column(String, default="23:59", nullable=False)

    # ── Metadatos opcionales ──────────────────────────────────────
    location = Column(String, nullable=True)       # descripción libre de ubicación
    manufacturer = Column(String, nullable=True)   # ej. "Hanwha"
    model = Column(String, nullable=True)          # ej. "XNO-6120R"


class CameraState(Base):
    """
    Estado en tiempo real de cada cámara.
    Se actualiza con cada evento de cruce de línea.
    """
    __tablename__ = "camera_states"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, unique=True, index=True)
    people_inside = Column(Integer, default=0, nullable=False)
    total_in = Column(Integer, default=0, nullable=False)
    total_out = Column(Integer, default=0, nullable=False)
    last_update = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # Normal | Advertencia | Crítico | Excedido
    status = Column(String, default="Normal", nullable=False)


class CountingEvent(Base):
    """
    Evento de conteo persistido en BD.
    Tipos: change_event | hourly_heartbeat | imported
    """
    __tablename__ = "counting_events"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True, nullable=False)
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    in_count = Column(Integer, nullable=False)
    out_count = Column(Integer, nullable=False)
    people_inside = Column(Integer, default=0)  # Aforo en ese instante
    # change_event | hourly_heartbeat | imported
    event_type = Column(String, nullable=False)
    location_group = Column(String, nullable=True)


class HourlyStat(Base):
    """
    Agregado por hora (bucket). Para reportes rápidos sin escanear toda la tabla.
    """
    __tablename__ = "hourly_stats"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True, nullable=False)
    hour_bucket = Column(DateTime, index=True, nullable=False)
    total_in = Column(Integer, nullable=False)
    total_out = Column(Integer, nullable=False)


class SystemSettings(Base):
    """
    Configuración editable desde el frontend (guardada en BD).
    Complementa el .env con preferencias de UI y umbrales de negocio.
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    update_interval = Column(Integer, default=3)          # segundos
    heartbeat_interval = Column(Integer, default=3600)    # segundos (1 hora)
    timezone = Column(String, default="America/Lima")
    date_format = Column(String, default="YYYY-MM-DD")
    time_format = Column(String, default="HH:mm:ss")
    warning_threshold = Column(Integer, default=80)       # % del aforo
    critical_threshold = Column(Integer, default=100)     # % del aforo
