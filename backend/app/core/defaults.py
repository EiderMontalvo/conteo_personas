"""Constantes de negocio compartidas por modelos y routers; no dependen del .env."""
from __future__ import annotations

# Umbrales de aforo (% del máximo). Default de columna en SystemSettings y
# fallback de /stats/capacity cuando no hay fila de settings en BD.
DEFAULT_WARNING_THRESHOLD: int = 80
DEFAULT_CRITICAL_THRESHOLD: int = 100