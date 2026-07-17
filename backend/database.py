"""
database.py
-----------
Configuración del motor de base de datos usando SQLAlchemy.
La URL se lee desde config.py
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator

from app.core.config import settings

#connect_args solo es necesario para SQLite
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: abre y cierra la sesión de BD por request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
