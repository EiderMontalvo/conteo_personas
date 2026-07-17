"""
Reexporta todos los modelos ORM para que el resto de la aplicación
solo importe desde `app.models` sin preocuparse por la ubicación interna.
"""
from app.models.counting import (  # noqa: F401
    Base,
    Camera,
    CameraState,
    CountingEvent,
    HourlyStat,
    SystemSettings,
)
