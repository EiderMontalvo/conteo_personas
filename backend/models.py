from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime, timezone
from database import Base

class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, unique=True, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)
    # Nuevos ajustes de cámara
    location = Column(String, nullable=True)
    zone = Column(String, nullable=True)
    max_capacity = Column(Integer, default=150)
    count_direction = Column(String, default="both")
    virtual_line = Column(String, nullable=True)
    operating_hours_start = Column(String, default="00:00")
    operating_hours_end = Column(String, default="23:59")

class CameraState(Base):
    __tablename__ = "camera_states"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, unique=True, index=True)
    people_inside = Column(Integer, default=0)
    total_in = Column(Integer, default=0)
    total_out = Column(Integer, default=0)
    last_update = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="Normal") # Normal, Advertencia, Crítico, Excedido

class SystemSettings(Base):
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    update_interval = Column(Integer, default=3)
    heartbeat_interval = Column(Integer, default=60)
    timezone = Column(String, default="America/Lima")
    date_format = Column(String, default="YYYY-MM-DD")
    time_format = Column(String, default="HH:mm:ss")
    warning_threshold = Column(Integer, default=80)
    critical_threshold = Column(Integer, default=100)

class CountingEvent(Base):
    __tablename__ = "counting_events"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    in_count = Column(Integer)
    out_count = Column(Integer)
    people_inside = Column(Integer, default=0) # NUEVO: Para guardar el aforo en ese instante
    # Tipos: 'change_event' | 'hourly_heartbeat' | 'imported'
    event_type = Column(String)
    location_group = Column(String, nullable=True)

class HourlyStat(Base):
    __tablename__ = "hourly_stats"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True)
    hour_bucket = Column(DateTime, index=True)
    total_in = Column(Integer)
    total_out = Column(Integer)
