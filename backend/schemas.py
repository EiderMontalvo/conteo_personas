from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CameraConfigUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    zone: Optional[str] = None
    max_capacity: Optional[int] = None
    count_direction: Optional[str] = None
    virtual_line: Optional[str] = None
    operating_hours_start: Optional[str] = None
    operating_hours_end: Optional[str] = None
    is_active: Optional[bool] = None

class SystemSettingsUpdate(BaseModel):
    update_interval: Optional[int] = None
    heartbeat_interval: Optional[int] = None
    timezone: Optional[str] = None
    date_format: Optional[str] = None
    time_format: Optional[str] = None
    warning_threshold: Optional[int] = None
    critical_threshold: Optional[int] = None

class CameraStateOut(BaseModel):
    people_inside: int
    total_in: int
    total_out: int
    last_update: datetime
    status: str
