"""
app/integrations/onvif/event_listener.py
------------------------------------------
CameraPoller + PollerPool — gestión dinámica del polling ONVIF.

CameraPoller: loop de polling para una sola cámara (puede reiniciarse).
PollerPool:   singleton que gestiona todos los CameraPoller activos.
              Permite agregar, recargar y eliminar cámaras en caliente
              sin reiniciar el servidor.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional

from app.core.config import settings
from app.integrations.onvif.client import OnvifCameraClient
from app.models.counting import Camera
from app.services.counting_service import counting_service

logger = logging.getLogger(__name__)


class CameraPoller:
    """
    Encapsula el loop de polling para UNA cámara.
    Se puede cancelar y reiniciar con una nueva IP sin recrear el objeto.
    """

    def __init__(self, camera: Camera) -> None:
        self._camera = camera
        self._client = OnvifCameraClient(
            ip=camera.ip_address,
            user=settings.camera_user,
            password=settings.camera_pass,
        )
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    @property
    def camera_id(self) -> int:
        return self._camera.camera_id

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """Arranca el loop de polling como tarea asyncio."""
        if self.is_running:
            return
        self._task = asyncio.create_task(
            self._loop(),
            name=f"poller-cam-{self._camera.camera_id}",
        )
        logger.info(
            "Poller iniciado: '%s' (%s) cada %ds.",
            self._camera.name, self._camera.ip_address, settings.poll_interval,
        )

    async def stop(self) -> None:
        """Cancela el loop de polling y espera que termine."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Poller detenido: '%s'.", self._camera.name)

    async def reload(self, updated_camera: Camera) -> None:
        """
        Recarga la configuración de la cámara (ej. nueva IP).
        Cancela el poller actual y arranca uno nuevo con la nueva config.
        """
        await self.stop()
        self._camera = updated_camera
        self._client.reset(updated_camera.ip_address)
        self.start()
        logger.info(
            "Poller recargado: '%s' → IP %s.",
            updated_camera.name, updated_camera.ip_address,
        )

    # ── Loop interno ───────────────────────────────────────────────

    async def _loop(self) -> None:
        """Ciclo principal de polling — se ejecuta hasta que se cancele."""
        from database import SessionLocal  # importación local para evitar ciclo

        while True:
            try:
                data = await self._client.get_realtime_count()

                if data is not None:
                    db = SessionLocal()
                    try:
                        await counting_service.process(
                            camera_id=self._camera.camera_id,
                            camera_name=self._camera.name,
                            camera_role=self._camera.role,
                            camera_group=self._camera.zone,
                            raw_in=data.in_count,
                            raw_out=data.out_count,
                            db=db,
                        )
                    finally:
                        db.close()

            except asyncio.CancelledError:
                logger.info("Polling cancelado: '%s'.", self._camera.name)
                return
            except Exception as exc:
                logger.exception(
                    "Error inesperado en poller '%s': %s", self._camera.name, exc
                )

            await asyncio.sleep(settings.poll_interval)


class PollerPool:
    """
    Singleton que gestiona el ciclo de vida de todos los CameraPoller.
    Permite operaciones en caliente: agregar, recargar y eliminar cámaras.
    """

    def __init__(self) -> None:
        self._pollers: Dict[int, CameraPoller] = {}

    async def start_all(self) -> None:
        """
        Lee las cámaras activas de la BD y arranca un poller por cada una.
        Llamado una sola vez en el lifespan de FastAPI.
        """
        from database import SessionLocal
        from app.repositories.camera_repo import camera_repo

        db = SessionLocal()
        try:
            cameras = camera_repo.get_active(db)
            logger.info("PollerPool: arrancando %d poller(s).", len(cameras))
            for cam in cameras:
                self._start_poller(cam)
        finally:
            db.close()

    async def stop_all(self) -> None:
        """Cancela todos los pollers activos (llamado en el shutdown de FastAPI)."""
        for poller in list(self._pollers.values()):
            await poller.stop()
        self._pollers.clear()
        logger.info("PollerPool: todos los pollers detenidos.")

    async def add_camera(self, camera: Camera) -> None:
        """Agrega y arranca un poller para una cámara recién creada."""
        if camera.camera_id in self._pollers:
            logger.warning(
                "PollerPool.add_camera: cámara %d ya tiene poller.", camera.camera_id
            )
            return
        self._start_poller(camera)

    async def reload_camera(self, updated_camera: Camera) -> None:
        """
        Recarga un poller existente con la nueva configuración de la cámara.
        Llamado después de PUT /api/v1/cameras/{id}.
        """
        cam_id = updated_camera.camera_id
        if cam_id in self._pollers:
            await self._pollers[cam_id].reload(updated_camera)
        else:
            # No existía poller (ej. estaba inactiva y se reactivó)
            self._start_poller(updated_camera)

    async def remove_camera(self, camera_id: int) -> None:
        """Cancela y elimina el poller de una cámara desactivada."""
        poller = self._pollers.pop(camera_id, None)
        if poller:
            await poller.stop()

    def _start_poller(self, camera: Camera) -> None:
        poller = CameraPoller(camera)
        poller.start()
        self._pollers[camera.camera_id] = poller

    def status(self) -> List[dict]:
        """Devuelve el estado de todos los pollers (para diagnóstico)."""
        return [
            {
                "camera_id": cam_id,
                "is_running": p.is_running,
            }
            for cam_id, p in self._pollers.items()
        ]


# Singleton compartido — inyectado via app.state en main.py
poller_pool = PollerPool()
