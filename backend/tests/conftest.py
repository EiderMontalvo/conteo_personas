"""
Configuración de pruebas: BD SQLite temporal y ajustes deterministas.
Las variables de entorno se fijan ANTES de importar la app, porque
app.core.config y database.py leen la configuración al importarse.
"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = tempfile.mkdtemp(prefix="conteo-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["DEMO_MODE"] = "false"
os.environ["TIMEZONE"] = "America/Lima"
os.environ["BUSINESS_HOUR_START"] = "0"
os.environ["BUSINESS_HOUR_END"] = "24"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

import database  # noqa: E402
from app.models.counting import Base  # noqa: E402,F401  (registra los modelos)


@pytest.fixture()
def db():
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    session = database.SessionLocal()
    try:
        yield session
    finally:
        session.close()
