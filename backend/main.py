"""Aplicación FastAPI: monta routers, CORS y el lifespan de los pollers."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
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

setup_logging()

Base.metadata.create_all(bind=database.engine)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    if settings.demo_mode:
        logging.getLogger(__name__).warning(
            "DEMO_MODE activo: los conteos son SIMULADOS, no se conecta a cámaras."
        )
    with database.SessionLocal() as db:
        camera_service.seed_from_env(db)   # Solo actúa si la tabla está vacía
    await poller_pool.start_all()
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

app.include_router(cameras.router,          prefix="/api/v1")
app.include_router(analytics.router,        prefix="/api/v1")
app.include_router(excel.router,            prefix="/api/v1")
app.include_router(settings_router.router,  prefix="/api/v1")
app.include_router(realtime.router)  # WebSocket sin prefijo (mantiene /ws/live)

# Alias legacy /api/... → /api/v1/... para el frontend antiguo
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


# ── Frontend compilado (npm run build) ───────────────────────────────────────
# Si existe frontend/dist, el backend sirve el dashboard en el mismo puerto:
# todo el sistema queda en http://localhost:8000 sin levantar Vite.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_NOT_SPA = ("api/", "ws/", "docs", "redoc", "openapi.json")

if (FRONTEND_DIST / "index.html").is_file():
    from fastapi import HTTPException
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    if (FRONTEND_DIST / "assets").is_dir():
        # Los nombres llevan hash: se pueden cachear para siempre.
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def frontend(path: str):
        if path.startswith(_NOT_SPA):
            raise HTTPException(status_code=404)
        file = (FRONTEND_DIST / path).resolve()
        if path and file.is_file() and FRONTEND_DIST in file.parents:
            return FileResponse(file)
        # Rutas de React Router (/analitica, /ajustes...) → index.html, sin caché
        return FileResponse(FRONTEND_DIST / "index.html", headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Servidor del sistema de conteo de personas")
    parser.add_argument("--reload", action="store_true", help="Recargar al cambiar código (desarrollo)")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("main:app", host="0.0.0.0", port=args.port, reload=args.reload)
