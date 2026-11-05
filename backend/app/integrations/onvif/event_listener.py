"""Pollers de eventos por cámara (reconexión con backoff) y su pool, editable en caliente.

Cada cambio de estado se emite por WebSocket como {"type": "camera_status", ...}.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.config import settings
from app.integrations.onvif.client import CameraConnectionError, OnvifCameraClient
from app.integrations.simulated import SimulatedCameraClient
from app.models.counting import Camera
from app.services.counting_service import counting_service
from app.websockets.connection_manager import ws_manager

logger = logging.getLogger(__name__)

# Estados de conexión expuestos al dashboard
CONNECTING = "connecting"
CONNECTED = "connected"
RECONNECTING = "reconnecting"
STOPPED = "stopped"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_client(camera: Camera):
    """Cliente real o simulado según DEMO_MODE."""
    if settings.demo_mode:
        return SimulatedCameraClient(camera.ip_address, pull_timeout=settings.poll_interval)
    return OnvifCameraClient(
        camera.ip_address,
        settings.camera_user,
        settings.camera_pass,
        port=settings.onvif_port,
        timeout=settings.onvif_timeout,
        pull_timeout=settings.poll_interval,
        subscription_ttl=settings.onvif_subscription_ttl,
        unsubscribe=settings.onvif_unsubscribe,
    )


class CameraPoller:
    """Escucha de eventos de UNA cámara. Se cancela con stop()."""

    def __init__(self, camera: Camera, client=None) -> None:
        self._camera = camera
        self._client = client or build_client(camera)
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

        self.state = STOPPED
        self.last_error: Optional[str] = None
        self.connected_since: Optional[datetime] = None
        self.last_event_at: Optional[datetime] = None
        self.next_retry_at: Optional[datetime] = None
        self.failures = 0  # fallos consecutivos (define el backoff)

    @property
    def camera_id(self) -> int:
        return self._camera.camera_id

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self.is_running:
            return
        self._task = asyncio.create_task(self._loop(), name=f"poller-cam-{self.camera_id}")
        logger.info(
            "Poller iniciado: '%s' (%s)%s.",
            self._camera.name, self._camera.ip_address,
            " [DEMO]" if settings.demo_mode else "",
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        try:
            await asyncio.wait_for(self._client.close(), timeout=settings.onvif_timeout + 2)
        except Exception as exc:
            logger.debug("Cierre de cliente '%s': %s", self._camera.name, exc)
        await self._set_state(STOPPED)
        logger.info("Poller detenido: '%s'.", self._camera.name)

    def snapshot(self) -> dict:
        iso = lambda d: d.isoformat() if d else None  # noqa: E731
        return {
            "camera_id": self.camera_id,
            "name": self._camera.name,
            "ip_address": self._camera.ip_address,
            "state": self.state,
            "demo": settings.demo_mode,
            "is_running": self.is_running,
            "last_error": self.last_error,
            "connected_since": iso(self.connected_since),
            "last_event_at": iso(self.last_event_at),
            "next_retry_at": iso(self.next_retry_at),
            "consecutive_failures": self.failures,
        }

    def _backoff_delay(self) -> float:
        return min(settings.reconnect_max_delay, 2 ** min(self.failures, 10))

    async def _set_state(self, state: str, error: Optional[str] = None) -> None:
        changed = state != self.state or error != self.last_error
        self.state = state
        self.last_error = error
        if changed:
            await ws_manager.broadcast({"type": "camera_status", "payload": self.snapshot()})

    async def _loop(self) -> None:
        from database import SessionLocal  # importación local para evitar ciclo

        await self._set_state(CONNECTING)
        while True:
            try:
                if not self._client.connected:
                    await self._client.connect()
                    self.failures = 0
                    self.connected_since = _now()
                    self.next_retry_at = None
                    await self._set_state(CONNECTED)

                data = await self._client.pull()

                if data.in_count or data.out_count:
                    self.last_event_at = _now()
                db = SessionLocal()
                try:
                    await counting_service.process(
                        camera_id=self._camera.camera_id,
                        camera_name=self._camera.name,
                        camera_role=self._camera.role,
                        camera_group=self._camera.zone,
                        max_capacity=self._camera.max_capacity,
                        raw_in=data.in_count,
                        raw_out=data.out_count,
                        db=db,
                    )
                finally:
                    db.close()

            except asyncio.CancelledError:
                raise
            except CameraConnectionError as exc:
                await self._on_failure(str(exc))
            except Exception as exc:  # fallo propio (BD, bug): no matar el poller
                logger.exception("Error inesperado en poller '%s'", self._camera.name)
                await self._on_failure(f"Error interno: {exc}")

    async def _on_failure(self, message: str) -> None:
        self.failures += 1
        self.connected_since = None
        delay = self._backoff_delay()
        self.next_retry_at = datetime.fromtimestamp(_now().timestamp() + delay, timezone.utc)
        logger.warning(
            "Cámara '%s' (%s): %s. Reintento en %.0fs (fallo #%d).",
            self._camera.name, self._camera.ip_address, message, delay, self.failures,
        )
        await self._set_state(RECONNECTING, message)
        await asyncio.sleep(delay)


class PollerPool:
    """Ciclo de vida de todos los CameraPoller activos."""

    def __init__(self) -> None:
        self._pollers: Dict[int, CameraPoller] = {}

    async def start_all(self) -> None:
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
        await asyncio.gather(*(p.stop() for p in self._pollers.values()), return_exceptions=True)
        self._pollers.clear()
        logger.info("PollerPool: todos los pollers detenidos.")

    async def add_camera(self, camera: Camera) -> None:
        if camera.camera_id in self._pollers:
            logger.warning("PollerPool.add_camera: cámara %d ya tiene poller.", camera.camera_id)
            return
        self._start_poller(camera)

    async def reload_camera(self, updated_camera: Camera) -> None:
        """Reemplaza el poller (libera la suscripción anterior y conecta con la nueva config)."""
        await self.remove_camera(updated_camera.camera_id)
        if updated_camera.is_active:
            self._start_poller(updated_camera)

    async def remove_camera(self, camera_id: int) -> None:
        poller = self._pollers.pop(camera_id, None)
        if poller:
            await poller.stop()

    def _start_poller(self, camera: Camera) -> None:
        poller = CameraPoller(camera)
        poller.start()
        self._pollers[camera.camera_id] = poller

    def get(self, camera_id: int) -> Optional[CameraPoller]:
        return self._pollers.get(camera_id)

    def status(self) -> List[dict]:
        return [p.snapshot() for p in self._pollers.values()]


poller_pool = PollerPool()
