import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATA_DIR = os.environ.get("DATA_DIR", "/data")
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DATA_DIR}/receipts.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI endpoints to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables."""
    from app import db_models  # noqa: F401 - Import needed for table creation
    Base.metadata.create_all(bind=engine)
