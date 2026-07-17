"""
app/repositories/camera_repo.py
--------------------------------
Repository específico para el modelo Camera + CameraState.
Único lugar que hace SQL sobre estas tablas.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.counting import Camera, CameraState
from app.repositories.base import GenericRepository

logger = logging.getLogger(__name__)


class CameraRepository(GenericRepository[Camera]):
    """Acceso a datos para cámaras."""

    def __init__(self) -> None:
        super().__init__(Camera)

    # ── Consultas específicas ──────────────────────────────────────

    def get_by_camera_id(self, db: Session, camera_id: int) -> Optional[Camera]:
        """Busca por el índice lógico (camera_id), no por PK de BD."""
        return db.query(Camera).filter(Camera.camera_id == camera_id).first()

    def get_by_ip(self, db: Session, ip: str) -> Optional[Camera]:
        return db.query(Camera).filter(Camera.ip_address == ip).first()

    def get_active(self, db: Session) -> List[Camera]:
        """Devuelve solo las cámaras activas (is_active=True)."""
        return db.query(Camera).filter(Camera.is_active == True).all()  # noqa: E712

    def next_camera_index(self, db: Session) -> int:
        """Devuelve el próximo índice lógico disponible (0, 1, 2...)."""
        cameras = db.query(Camera.camera_id).all()
        existing = {c.camera_id for c in cameras}
        idx = 0
        while idx in existing:
            idx += 1
        return idx

    def seed_from_env(self, db: Session, env_cameras: list[dict]) -> None:
        """
        Inserta cámaras desde el .env SOLO si la tabla está completamente vacía.
        Permite que el .env funcione como configuración inicial sin sobrescribir
        los cambios hechos desde el frontend.
        """
        if db.query(Camera).count() > 0:
            logger.debug("Tabla cameras ya tiene datos — seed omitido.")
            return
        for cam_data in env_cameras:
            db.add(Camera(**cam_data))
        db.commit()
        logger.info("Semilla de %d cámara(s) desde .env aplicada.", len(env_cameras))

    # ── Estado en tiempo real ──────────────────────────────────────

    def get_state(self, db: Session, camera_id: int) -> Optional[CameraState]:
        return db.query(CameraState).filter(CameraState.camera_id == camera_id).first()

    def upsert_state(
        self,
        db: Session,
        camera_id: int,
        people_inside: int,
        total_in: int,
        total_out: int,
        status: str,
    ) -> CameraState:
        """Crea o actualiza el estado en tiempo real de una cámara."""
        state = self.get_state(db, camera_id)
        if state is None:
            state = CameraState(camera_id=camera_id)
            db.add(state)
        state.people_inside = people_inside
        state.total_in = total_in
        state.total_out = total_out
        state.status = status
        db.commit()
        db.refresh(state)
        return state


# Instancia singleton para inyectar por dependencia
camera_repo = CameraRepository()
