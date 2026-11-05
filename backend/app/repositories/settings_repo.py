"""Acceso a la fila única de SystemSettings."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models.counting import SystemSettings
from app.repositories.base import GenericRepository

logger = logging.getLogger(__name__)


class SystemSettingsRepository(GenericRepository[SystemSettings]):
    def __init__(self) -> None:
        super().__init__(SystemSettings)

    def get_singleton(self, db: Session) -> SystemSettings:
        """Crea la fila con defaults si no existe."""
        s = db.query(SystemSettings).first()
        if s is None:
            s = SystemSettings()
            db.add(s)
            db.commit()
            db.refresh(s)
            logger.info("SystemSettings no existía — creada con defaults.")
        return s

    def update_singleton(self, db: Session, data: dict) -> SystemSettings:
        """Actualización parcial; crea la fila con defaults si no existía."""
        s = self.get_singleton(db)
        return self.update(db, s, data)


settings_repo = SystemSettingsRepository()