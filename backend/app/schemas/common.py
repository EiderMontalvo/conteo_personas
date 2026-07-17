"""
app/schemas/common.py
---------------------
Sobre de respuesta estándar para toda la API.
Todos los endpoints devuelven ApiResponse[T] — nunca dicts ad-hoc.
"""
from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Sobre estándar de éxito/error para toda la API."""
    ok: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
    total: Optional[int] = None

    @classmethod
    def success(cls, data: T, total: Optional[int] = None) -> "ApiResponse[T]":
        return cls(ok=True, data=data, total=total)

    @classmethod
    def fail(cls, error: str) -> "ApiResponse[None]":
        return cls(ok=False, error=error)


class PaginationParams(BaseModel):
    """Parámetros de paginación reutilizables."""
    limit: int = 500
    offset: int = 0
