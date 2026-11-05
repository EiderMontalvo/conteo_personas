"""Modelos ORM SQLAlchemy del sistema de conteo de personas."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

# Única declarative_base() del proyecto: si hubiera otra, main.py crearía
# tablas con un metadata vacío.
from database import Base

from app.core.defaults import DEFAULT_CRITICAL_THRESHOLD, DEFAULT_WARNING_THRESHOLD


class Camera(Base):
    """Cámara física. El PollerPool lee su configuración de esta tabla, no del .env."""
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    # Índice lógico (0, 1, 2...); corresponde a CAMERA_{n}_* en el .env.
    camera_id = Column(Integer, unique=True, index=True)
    ip_address = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # both | in_only | out_only | space. space vigila un espacio cerrado y
    # cuenta entradas y salidas, igual que both.
    role = Column(String, default="both", nullable=False)
    # Cámaras con la misma zona se consolidan en reportes.
    zone = Column(String, nullable=True)
    max_capacity = Column(Integer, default=150, nullable=False)

    operating_hours_start = Column(String, default="00:00", nullable=False)
    operating_hours_end = Column(String, default="23:59", nullable=False)

    location = Column(String, nullable=True)
    manufacturer = Column(String, nullable=True)   # ej. "Hanwha"
    model = Column(String, nullable=True)          # ej. "XNO-6120R"


class CameraState(Base):
    """Estado en tiempo real de cada cámara; se actualiza con cada cruce de línea."""
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
    """Evento de conteo persistido."""
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
    people_inside = Column(Integer, default=0)  # aforo en ese instante
    # change_event | hourly_heartbeat | imported
    event_type = Column(String, nullable=False)
    location_group = Column(String, nullable=True)


class HourlyStat(Base):
    """Agregado por hora, para reportes sin escanear counting_events."""
    __tablename__ = "hourly_stats"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True, nullable=False)
    hour_bucket = Column(DateTime, index=True, nullable=False)
    total_in = Column(Integer, nullable=False)
    total_out = Column(Integer, nullable=False)


class SystemSettings(Base):
    """Preferencias de UI y umbrales de negocio editables desde el frontend."""
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    update_interval = Column(Integer, default=3)          # segundos
    heartbeat_interval = Column(Integer, default=3600)    # segundos
    timezone = Column(String, default="America/Lima")
    date_format = Column(String, default="YYYY-MM-DD")
    time_format = Column(String, default="HH:mm:ss")
    warning_threshold = Column(Integer, default=DEFAULT_WARNING_THRESHOLD)       # % del aforo
    critical_threshold = Column(Integer, default=DEFAULT_CRITICAL_THRESHOLD)     # % del aforo
