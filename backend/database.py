"""Motor y sesiones SQLAlchemy; la URL viene de settings.database_url."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator

from app.core.config import settings

# check_same_thread solo aplica a SQLite
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Único declarative_base(): los modelos deben importar Base de aquí.
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependencia de FastAPI: una sesión de BD por request."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
