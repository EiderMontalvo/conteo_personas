from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime, timezone
from database import Base

class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    ip_address = Column(String, unique=True, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)

class CountingEvent(Base):
    __tablename__ = "counting_events"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    in_count = Column(Integer)
    out_count = Column(Integer)
    event_type = Column(String) #'real_time' or 'historical_sync'

class HourlyStat(Base):
    __tablename__ = "hourly_stats"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True)
    hour_bucket = Column(DateTime, index=True)
    total_in = Column(Integer)
    total_out = Column(Integer)
