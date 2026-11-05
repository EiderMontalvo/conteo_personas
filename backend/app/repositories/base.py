"""Repositorio CRUD genérico; las operaciones reciben la sesión, nunca crean una."""
from __future__ import annotations

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from app.models.counting import Base

ModelType = TypeVar("ModelType", bound=Base)


class GenericRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]) -> None:
        self._model = model

    def get(self, db: Session, record_id: int) -> Optional[ModelType]:
        return db.query(self._model).filter(self._model.id == record_id).first()

    def get_all(self, db: Session, *, limit: int = 1000, offset: int = 0) -> List[ModelType]:
        return db.query(self._model).offset(offset).limit(limit).all()

    def create(self, db: Session, obj: ModelType) -> ModelType:
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, obj: ModelType, data: dict) -> ModelType:
        """Ignora las claves de `data` que no son atributos del modelo."""
        for field, value in data.items():
            if hasattr(obj, field):
                setattr(obj, field, value)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, record_id: int) -> bool:
        """Devuelve True si el registro existía."""
        obj = self.get(db, record_id)
        if obj is None:
            return False
        db.delete(obj)
        db.commit()
        return True
