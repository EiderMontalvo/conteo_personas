"""
app/core/logging.py
-------------------
Configuración de logging estructurado centralizada.
Importar y llamar a setup_logging() desde main.py antes de arrancar la app.
"""
from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el formato de log para toda la aplicación."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
    # Silenciar logs muy verbosos de librerías externas
    logging.getLogger("zeep").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
