"""
app/services/camera_service.py
--------------------------------
Lógica de negocio para gestionar cámaras.
Orquesta: BD (repository) + .env (env_writer) + polling (poller_pool).

Regla de dependencia: este service NO importa nada de app/api.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.counting import Camera
from app.repositories.camera_repo import camera_repo
from app.schemas.camera import CameraCreate, CameraUpdate
from app.services.env_writer import EnvWriter

logger = logging.getLogger(__name__)

# Ruta al .env (relativa a la raíz del backend)
_ENV_PATH = Path(__file__).parent.parent.parent.parent / ".env"
_env_writer = EnvWriter(_ENV_PATH)


class CameraService:
    """
    Gestión completa del ciclo de vida de una cámara:
    crear, actualizar, desactivar — manteniendo BD y .env sincronizados,
    y notificando al PollerPool para que reconecte en caliente.
    """

    async def get_all(self, db: Session) -> List[Camera]:
        """Devuelve todas las cámaras activas."""
        return camera_repo.get_active(db)

    async def get_by_id(self, db: Session, camera_pk: int) -> Optional[Camera]:
        """Busca por PK de BD."""
        return camera_repo.get(db, camera_pk)

    async def create(self, db: Session, data: CameraCreate) -> Camera:
        """
        Crea una cámara nueva:
        1. Asigna índice lógico.
        2. Inserta en BD.
        3. Actualiza .env.
        4. Arranca su poller.
        """
        from app.integrations.onvif.event_listener import poller_pool

        index = camera_repo.next_camera_index(db)
        cam = Camera(
            camera_id=index,
            ip_address=data.ip_address,
            name=data.name,
            role=data.role,
            zone=data.zone,
            max_capacity=data.max_capacity,
            location=data.location,
            operating_hours_start=data.operating_hours_start,
            operating_hours_end=data.operating_hours_end,
            is_active=True,
        )
        db.add(cam)
        db.commit()
        db.refresh(cam)

        # Actualizar .env
        _env_writer.set_camera(
            index,
            ip=data.ip_address,
            name=data.name,
            role=data.role,
            group=data.zone,
        )

        # Arrancar poller
        await poller_pool.add_camera(cam)
        logger.info("Cámara creada: '%s' (%s), índice %d.", cam.name, cam.ip_address, index)
        return cam

    async def update(self, db: Session, camera_pk: int, data: CameraUpdate) -> Optional[Camera]:
        """
        Actualiza una cámara:
        1. Modifica en BD.
        2. Si cambió IP/nombre/rol/grupo → actualiza .env.
        3. Recarga el poller (se reconecta con la nueva IP).
        """
        from app.integrations.onvif.event_listener import poller_pool

        cam = camera_repo.get(db, camera_pk)
        if cam is None:
            return None

        update_dict = data.model_dump(exclude_unset=True)
        cam = camera_repo.update(db, cam, update_dict)

        # Sincronizar .env si cambió algo relevante para el poller
        env_fields = {"ip_address", "name", "role", "zone"}
        if env_fields & set(update_dict.keys()):
            _env_writer.set_camera(
                cam.camera_id,
                ip=cam.ip_address,
                name=cam.name,
                role=cam.role,
                group=cam.zone,
            )

        # Recargar poller
        await poller_pool.reload_camera(cam)
        logger.info(
            "Cámara actualizada: '%s' (%s). Poller recargado.", cam.name, cam.ip_address
        )
        return cam

    async def deactivate(self, db: Session, camera_pk: int) -> bool:
        """
        Desactiva una cámara (is_active=False), cancela su poller y
        comenta sus entradas en el .env.
        """
        from app.integrations.onvif.event_listener import poller_pool

        cam = camera_repo.get(db, camera_pk)
        if cam is None:
            return False

        camera_repo.update(db, cam, {"is_active": False})
        await poller_pool.remove_camera(cam.camera_id)
        _env_writer.remove_camera(cam.camera_id)
        logger.info("Cámara desactivada: '%s'.", cam.name)
        return True

    def seed_from_env(self, db: Session) -> None:
        """
        Inicializa la tabla Camera desde el .env (solo si está vacía).
        Lee el formato legacy CAMERA_{n}_IP / CAMERA_{n}_NAME / CAMERA_{n}_ROLE.
        """
        import os
        from app.core.config import settings as cfg

        if camera_repo.get_all(db, limit=1):
            return  # Ya hay cámaras en BD

        index = 0
        while True:
            ip = os.getenv(f"CAMERA_{index}_IP")
            if ip is None:
                break
            name = os.getenv(f"CAMERA_{index}_NAME", f"Cámara {index}")
            role = os.getenv(f"CAMERA_{index}_ROLE", "both").lower()
            group = os.getenv(f"CAMERA_{index}_GROUP")
            db.add(Camera(
                camera_id=index,
                ip_address=ip,
                name=name,
                role=role,
                zone=group,
                is_active=True,
            ))
            index += 1

        if index > 0:
            db.commit()
            logger.info("Semilla desde .env: %d cámara(s) creadas.", index)


# Singleton
camera_service = CameraService()
