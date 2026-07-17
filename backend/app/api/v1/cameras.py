"""
app/api/v1/cameras.py
----------------------
Router de cámaras. SOLO orquesta — sin lógica de negocio.
Toda la lógica vive en CameraService / discovery.py.
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import database
from app.integrations.onvif.discovery import discover_cameras
from app.repositories.camera_repo import camera_repo
from app.schemas.camera import CameraCreate, CameraOut, CameraUpdate, DiscoveredCamera
from app.schemas.common import ApiResponse
from app.services.camera_service import camera_service

router = APIRouter(prefix="/cameras", tags=["Cámaras"])
logger = logging.getLogger(__name__)


def _db():
    yield from database.get_db()


# ── GET /cameras ──────────────────────────────────────────────────

@router.get(
    "",
    response_model=ApiResponse[List[CameraOut]],
    summary="Lista las cámaras configuradas",
    description="Devuelve todas las cámaras activas con su configuración y estado en tiempo real.",
)
async def list_cameras(db: Session = Depends(_db)):
    cameras = await camera_service.get_all(db)
    # Enriquecer con estado en tiempo real
    result: List[CameraOut] = []
    for cam in cameras:
        state = camera_repo.get_state(db, cam.camera_id)
        cam_out = CameraOut.model_validate(cam)
        if state:
            cam_out.people_inside = state.people_inside
            cam_out.total_in = state.total_in
            cam_out.total_out = state.total_out
            cam_out.status = state.status
        result.append(cam_out)
    return ApiResponse.success(result, total=len(result))


# ── GET /cameras/discover ─────────────────────────────────────────

@router.get(
    "/discover",
    response_model=ApiResponse[List[DiscoveredCamera]],
    summary="Escanear red para encontrar cámaras ONVIF",
    description=(
        "Usa WS-Discovery (ONVIF estándar) + TCP scan como fallback "
        "para encontrar cámaras en la red local. Puede tardar 5-15 segundos."
    ),
)
async def discover(db: Session = Depends(_db)):
    discovered = await discover_cameras()
    # Marcar cuáles ya están en BD
    existing_ips = {c.ip_address for c in camera_repo.get_all(db, limit=1000)}
    for cam in discovered:
        cam.already_added = cam.ip in existing_ips
    return ApiResponse.success(discovered, total=len(discovered))


# ── POST /cameras ─────────────────────────────────────────────────

@router.post(
    "",
    response_model=ApiResponse[CameraOut],
    status_code=status.HTTP_201_CREATED,
    summary="Agregar una cámara nueva",
    description="Crea la cámara en BD, la registra en el .env y arranca su poller automáticamente.",
)
async def create_camera(data: CameraCreate, db: Session = Depends(_db)):
    # Verificar que la IP no esté duplicada
    existing = camera_repo.get_by_ip(db, data.ip_address)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una cámara con la IP {data.ip_address}.",
        )
    cam = await camera_service.create(db, data)
    return ApiResponse.success(CameraOut.model_validate(cam))


# ── GET /cameras/{id} ─────────────────────────────────────────────

@router.get(
    "/{camera_pk}",
    response_model=ApiResponse[CameraOut],
    summary="Detalle de una cámara",
)
async def get_camera(camera_pk: int, db: Session = Depends(_db)):
    cam = await camera_service.get_by_id(db, camera_pk)
    if cam is None:
        raise HTTPException(status_code=404, detail="Cámara no encontrada.")
    state = camera_repo.get_state(db, cam.camera_id)
    cam_out = CameraOut.model_validate(cam)
    if state:
        cam_out.people_inside = state.people_inside
        cam_out.total_in = state.total_in
        cam_out.total_out = state.total_out
        cam_out.status = state.status
    return ApiResponse.success(cam_out)


# ── PUT /cameras/{id} ─────────────────────────────────────────────

@router.put(
    "/{camera_pk}",
    response_model=ApiResponse[CameraOut],
    summary="Actualizar configuración de cámara",
    description=(
        "Actualiza nombre, IP, rol, aforo u horario. "
        "Si cambia la IP, el poller se reconecta automáticamente sin reiniciar el servidor. "
        "El archivo .env también se actualiza."
    ),
)
async def update_camera(camera_pk: int, data: CameraUpdate, db: Session = Depends(_db)):
    cam = await camera_service.update(db, camera_pk, data)
    if cam is None:
        raise HTTPException(status_code=404, detail="Cámara no encontrada.")
    return ApiResponse.success(CameraOut.model_validate(cam))


# ── DELETE /cameras/{id} ──────────────────────────────────────────

@router.delete(
    "/{camera_pk}",
    response_model=ApiResponse[None],
    summary="Desactivar una cámara",
    description="Marca la cámara como inactiva, cancela su poller y comenta su entrada en el .env.",
)
async def deactivate_camera(camera_pk: int, db: Session = Depends(_db)):
    ok = await camera_service.deactivate(db, camera_pk)
    if not ok:
        raise HTTPException(status_code=404, detail="Cámara no encontrada.")
    return ApiResponse.success(None)
