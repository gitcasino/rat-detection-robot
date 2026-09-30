"""SQLAlchemy engine, session factory and declarative base."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _enable_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    connect_args = {"check_same_thread": False, "timeout": 15} if settings.is_sqlite else {}
    engine = create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )
    if settings.is_sqlite:

        @event.listens_for(engine, "connect")
        def _on_connect(dbapi_connection, connection_record):  # pragma: no cover - driver hook
            _enable_sqlite_pragmas(dbapi_connection, connection_record)

    return engine


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    from app import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(bind=get_engine())


def reset_engine() -> None:
    """Drop cached engine/session factory. Used by tests that swap the database URL."""
    get_engine.cache_clear()
    get_session_factory.cache_clear()
