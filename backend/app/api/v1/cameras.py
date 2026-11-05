"""Endpoints de cámaras; la lógica vive en CameraService y discovery.py."""
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


def _video_camera(db: Session, camera_pk: int):
    from app.core.config import settings

    cam = camera_repo.get(db, camera_pk)
    if cam is None or not cam.is_active:
        raise HTTPException(status_code=404, detail="Cámara no encontrada.")
    if settings.demo_mode:
        raise HTTPException(status_code=503, detail="Sin video en modo demo: no hay cámara conectada.")
    return cam


@router.get(
    "/{camera_pk}/snapshot",
    summary="Imagen actual de la cámara (JPEG)",
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def camera_snapshot(camera_pk: int, db: Session = Depends(database.get_db)):
    from fastapi.responses import Response
    from app.integrations.video import VideoUnavailable, fetch_snapshot

    cam = _video_camera(db, camera_pk)
    try:
        jpeg = await fetch_snapshot(cam.ip_address)
    except VideoUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get(
    "/{camera_pk}/stream",
    summary="Video en vivo (MJPEG)",
    description="Para usar directo en un <img>. Retransmite el MJPEG de la cámara o, si no lo ofrece, snapshots a ~2 fps.",
)
async def camera_stream(camera_pk: int, db: Session = Depends(database.get_db)):
    from fastapi.responses import StreamingResponse
    from app.integrations.video import VideoUnavailable, open_mjpeg

    cam = _video_camera(db, camera_pk)
    try:
        media_type, body = await open_mjpeg(cam.ip_address)
    except VideoUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return StreamingResponse(body, media_type=media_type, headers={"Cache-Control": "no-store"})


@router.get(
    "/{camera_pk}/iva-lines",
    summary="Líneas virtuales IVA configuradas en la cámara",
    description="Coordenadas en el espacio width x height que devuelve, para dibujarlas sobre el video.",
)
async def camera_iva_lines(camera_pk: int, db: Session = Depends(database.get_db)):
    from app.integrations.video import VideoUnavailable, fetch_iva_lines

    cam = _video_camera(db, camera_pk)
    try:
        data = await fetch_iva_lines(cam.ip_address)
    except VideoUnavailable as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ApiResponse.success(data)


@router.get(
    "",
    response_model=ApiResponse[List[CameraOut]],
    summary="Lista las cámaras configuradas",
    description="Devuelve todas las cámaras activas con su configuración y estado en tiempo real.",
)
async def list_cameras(db: Session = Depends(database.get_db)):
    cameras = await camera_service.get_all(db)
    result = [_to_out(db, cam) for cam in cameras]
    return ApiResponse.success(result, total=len(result))


def _to_out(db: Session, cam) -> CameraOut:
    """CameraOut enriquecido con el estado del día y el de la conexión."""
    from app.integrations.onvif.event_listener import poller_pool

    cam_out = CameraOut.model_validate(cam)
    state = camera_repo.get_state(db, cam.camera_id)
    if state:
        cam_out.people_inside = state.people_inside
        cam_out.total_in = state.total_in
        cam_out.total_out = state.total_out
        cam_out.status = state.status
    poller = poller_pool.get(cam.camera_id)
    if poller:
        cam_out.connection = poller.snapshot()
    return cam_out


# Declarado antes de /{camera_pk} para que "status" no se tome como id.
@router.get(
    "/status",
    response_model=ApiResponse[List[dict]],
    summary="Estado de conexión de cada cámara",
    description=(
        "connecting | connected | reconnecting | stopped, con último error, "
        "próximo reintento y fallos consecutivos. Los cambios también se "
        "emiten por /ws/live como mensajes type='camera_status'."
    ),
)
async def cameras_status():
    from app.integrations.onvif.event_listener import poller_pool

    data = poller_pool.status()
    return ApiResponse.success(data, total=len(data))


@router.get(
    "/discover",
    response_model=ApiResponse[List[DiscoveredCamera]],
    summary="Escanear red para encontrar cámaras ONVIF",
    description=(
        "Usa WS-Discovery (ONVIF estándar) + TCP scan como fallback "
        "para encontrar cámaras en la red local. Puede tardar 5-15 segundos."
    ),
)
async def discover(db: Session = Depends(database.get_db)):
    discovered = await discover_cameras()
    existing_ips = {c.ip_address for c in camera_repo.get_active(db)}
    for cam in discovered:
        cam.already_added = cam.ip in existing_ips
    return ApiResponse.success(discovered, total=len(discovered))


@router.post(
    "",
    response_model=ApiResponse[CameraOut],
    status_code=status.HTTP_201_CREATED,
    summary="Agregar una cámara nueva",
    description="Crea la cámara en BD, la registra en el .env y arranca su poller automáticamente.",
)
async def create_camera(data: CameraCreate, db: Session = Depends(database.get_db)):
    # IP repetida: error si está activa, se reactiva si no.
    existing = camera_repo.get_by_ip(db, data.ip_address)
    if existing:
        if existing.is_active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una cámara activa con la IP {data.ip_address}.",
            )
        else:
            update_data = CameraUpdate(**data.model_dump(), is_active=True)
            cam = await camera_service.update(db, existing.id, update_data)
            return ApiResponse.success(CameraOut.model_validate(cam))

    cam = await camera_service.create(db, data)
    return ApiResponse.success(CameraOut.model_validate(cam))


@router.get(
    "/{camera_pk}",
    response_model=ApiResponse[CameraOut],
    summary="Detalle de una cámara",
)
async def get_camera(camera_pk: int, db: Session = Depends(database.get_db)):
    cam = await camera_service.get_by_id(db, camera_pk)
    if cam is None:
        raise HTTPException(status_code=404, detail="Cámara no encontrada.")
    return ApiResponse.success(_to_out(db, cam))


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
async def update_camera(camera_pk: int, data: CameraUpdate, db: Session = Depends(database.get_db)):
    cam = await camera_service.update(db, camera_pk, data)
    if cam is None:
        raise HTTPException(status_code=404, detail="Cámara no encontrada.")
    return ApiResponse.success(CameraOut.model_validate(cam))


@router.delete(
    "/{camera_pk}",
    response_model=ApiResponse[None],
    summary="Desactivar una cámara",
    description="Marca la cámara como inactiva, cancela su poller y comenta su entrada en el .env.",
)
async def deactivate_camera(camera_pk: int, db: Session = Depends(database.get_db)):
    ok = await camera_service.deactivate(db, camera_pk)
    if not ok:
        raise HTTPException(status_code=404, detail="Cámara no encontrada.")
    return ApiResponse.success(None)
