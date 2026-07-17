"""
main.py
-------
Composition root de la aplicación FastAPI.
≤50 líneas: solo monta routers, configura middlewares y gestiona el lifespan.
Toda la lógica de negocio vive en app/.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.integrations.onvif.event_listener import poller_pool
from app.services.camera_service import camera_service
from app.api.v1 import cameras, analytics, realtime, excel
from app.api.v1 import settings as settings_router
from app.models.counting import Base
import database

# Configurar logging antes de cualquier otra cosa
setup_logging()

# Crear tablas (idempotente)
Base.metadata.create_all(bind=database.engine)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ciclo de vida: seed de cámaras desde .env → arrancar pollers."""
    with database.SessionLocal() as db:
        camera_service.seed_from_env(db)   # Solo actúa si la tabla está vacía
    await poller_pool.start_all()           # Arranca un poller por cámara activa
    yield
    await poller_pool.stop_all()


app = FastAPI(
    title="Conteo de Personas API",
    description=(
        "Sistema de monitorización en tiempo real del flujo de personas "
        "con cámaras Hanwha Wisenet vía ONVIF."
    ),
    version="4.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Montar routers ─────────────────────────────────────────────────
app.include_router(cameras.router,          prefix="/api/v1")
app.include_router(analytics.router,        prefix="/api/v1")
app.include_router(excel.router,            prefix="/api/v1")
app.include_router(settings_router.router,  prefix="/api/v1")
app.include_router(realtime.router)  # WebSocket sin prefijo (mantiene /ws/live)

# ── Retrocompatibilidad: alias de rutas legacy (/api/... → /api/v1/...) ───────
# Permite que el frontend viejo siga funcionando sin cambios inmediatos
from fastapi.responses import RedirectResponse

@app.get("/api/cameras", include_in_schema=False)
def legacy_cameras():
    return RedirectResponse("/api/v1/cameras")

@app.get("/api/cameras/config", include_in_schema=False)
def legacy_cameras_config():
    return RedirectResponse("/api/v1/cameras")

@app.get("/api/stats/historical", include_in_schema=False)
def legacy_historical():
    return RedirectResponse("/api/v1/stats/historical")

@app.get("/api/settings", include_in_schema=False)
def legacy_settings_get():
    return RedirectResponse("/api/v1/settings")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
