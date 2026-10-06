"""SQLAlchemy User model."""
import os
import uuid
import logging
import time
from sqlalchemy.exc import OperationalError
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _resolve_database_url():
    postgres_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
    if postgres_url:
        if postgres_url.startswith("postgres://"):
            postgres_url = "postgresql://" + postgres_url[len("postgres://"):]
        if not postgres_url.startswith(("postgresql://", "postgresql+psycopg2://")):
            raise RuntimeError("POSTGRES_URL/DATABASE_URL must be a PostgreSQL URL")
        return postgres_url
    if os.getenv("USE_SQLITE", "false").lower() in {"1", "true", "yes", "on"}:
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "user_management.db"))
        return f"sqlite:///{db_path}"
    raise RuntimeError("Configure POSTGRES_URL or DATABASE_URL, or explicitly set USE_SQLITE=true for local development")


DATABASE_URL = _resolve_database_url()
engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

else:
    engine_kwargs["connect_args"] = {"connect_timeout": 5}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    for attempt in range(1, 6):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError:
            if attempt == 5:
                raise RuntimeError("Database initialization failed after 5 attempts; check database configuration and availability") from None
            logging.getLogger(__name__).warning("Database unavailable; retrying initialization (%s/5)", attempt)
            time.sleep(2)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
