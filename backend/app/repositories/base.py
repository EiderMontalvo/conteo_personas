"""
app/repositories/base.py
------------------------
Repository genérico reutilizable con operaciones CRUD básicas.
Todas las operaciones reciben una sesión de BD inyectada — nunca crean la suya propia.
"""
from __future__ import annotations

from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy.orm import Session

from app.models.counting import Base

ModelType = TypeVar("ModelType", bound=Base)


class GenericRepository(Generic[ModelType]):
    """
    CRUD genérico. Subclasificar para añadir métodos de negocio específicos.
    Principio DRY: nadie más repite get_by_id / create / update / delete.
    """

    def __init__(self, model: Type[ModelType]) -> None:
        self._model = model

    def get(self, db: Session, record_id: int) -> Optional[ModelType]:
        """Obtiene un registro por su PK o None si no existe."""
        return db.query(self._model).filter(self._model.id == record_id).first()

    def get_all(self, db: Session, *, limit: int = 1000, offset: int = 0) -> List[ModelType]:
        """Devuelve todos los registros con paginación simple."""
        return db.query(self._model).offset(offset).limit(limit).all()

    def create(self, db: Session, obj: ModelType) -> ModelType:
        """Persiste un objeto nuevo y lo refresca desde BD."""
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def update(self, db: Session, obj: ModelType, data: dict) -> ModelType:
        """
        Actualiza los campos indicados en `data` sobre `obj`.
        Solo actualiza campos que existan en el modelo.
        """
        for field, value in data.items():
            if hasattr(obj, field):
                setattr(obj, field, value)
        db.commit()
        db.refresh(obj)
        return obj

    def delete(self, db: Session, record_id: int) -> bool:
        """Elimina el registro por PK. Devuelve True si existía."""
        obj = self.get(db, record_id)
        if obj is None:
            return False
        db.delete(obj)
        db.commit()
        return True
