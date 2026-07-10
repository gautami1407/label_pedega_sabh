"""PostgreSQL database session management."""

from __future__ import annotations

from collections.abc import Generator
import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

from lps.core.config import get_settings
import logging
from pathlib import Path
import os




_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


class Base(DeclarativeBase):
    pass


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict = {}

        # database_url is stored as a plain string in Settings to avoid URL-encoding filesystem paths.
        db_url = getattr(settings, "database_url_str", None) or str(settings.database_url)


        if db_url.startswith("sqlite"):
            # Ensure parent directory exists for file-based SQLite.
            connect_args = {"check_same_thread": False}

            # Supported formats:
            # - sqlite:///absolute/path.db
            # - sqlite:///:memory:
            if db_url.startswith("sqlite:///") and not db_url.endswith(":"):
                # Strip scheme; keep path as a filesystem path (no URL decoding beyond spaces).
                db_path = db_url[len("sqlite:///") :]

                # Observed failure indicates URL-encoded spaces (%20) get through.
                db_path = db_path.replace("%20", " ")

                # Also handle accidental %2F/%5C style encodings in case they appear.
                db_path = db_path.replace("%5C", "\\").replace("%2F", "/")

                from pathlib import Path

                db_path_obj = Path(db_path)
                if db_path_obj.parent:
                    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
                if not db_path_obj.exists():
                    db_path_obj.touch(exist_ok=True)

        # Optional debug hook (disabled by default) to inspect resolved sqlite URLs.
        # Set env var LPS_DEBUG_SQLITE_URL=1 to enable.
        if os.getenv("LPS_DEBUG_SQLITE_URL") == "1":
            print("[lps][debug] DATABASE_URL:", os.getenv("DATABASE_URL"))
            print("[lps][debug] resolved db_url:", db_url)

        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        # Validate connection early — if Postgres is unreachable, fall back to a local sqlite file
        try:
            # attempt a short-lived connection to validate availability
            with _engine.connect() as _conn:
                pass
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning("PostgreSQL unavailable at %s — falling back to local sqlite: %s", db_url, e)
            # Create an on-disk sqlite database inside the backend directory
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sqlite_path = os.path.join(backend_dir, "local_lps.db")
            sqlite_url = f"sqlite:///{sqlite_path}"
            # ensure parent directory exists
            try:
                Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass

            _engine = create_engine(
                sqlite_url,
                pool_pre_ping=True,
                connect_args={"check_same_thread": False},
            )
    return _engine





def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _session_factory


class _EngineProxy:
    def connect(self, *args, **kwargs):
        return get_engine().connect(*args, **kwargs)

    def dispose(self, *args, **kwargs):
        return get_engine().dispose(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(get_engine(), item)


class _SessionLocalProxy:
    def __call__(self, *args, **kwargs):
        return get_session_factory()(*args, **kwargs)


engine = _EngineProxy()
SessionLocal = _SessionLocalProxy()


def get_db() -> Generator:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from lps.shared.models import history as _history_models  # noqa: F401
    from lps.shared.models import user as _user_models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())


def reset_db_connections() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None

