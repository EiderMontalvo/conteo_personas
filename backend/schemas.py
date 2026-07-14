from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CameraBase(BaseModel):
    ip_address: str
    name: str
    is_active: bool = True

class CameraCreate(CameraBase):
    pass

class Camera(CameraBase):
    id: int

    class Config:
        from_attributes = True

class CountingEventBase(BaseModel):
    in_count: int
    out_count: int
    event_type: str

class CountingEventCreate(CountingEventBase):
    camera_id: int

class CountingEvent(CountingEventBase):
    id: int
    camera_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

class HourlyStat(BaseModel):
    id: int
    camera_id: int
    hour_bucket: datetime
    total_in: int
    total_out: int

    class Config:
        from_attributes = True
        
class LiveData(BaseModel):
    timestamp: str
    in_count: int
    out_count: int
    
