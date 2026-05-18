from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

from echo.config import settings


def _make_engine(url: str):
    """Build the SQLAlchemy engine with sqlite-friendly defaults for tests.

    Postgres (prod) needs no special args. SQLite needs:
    - check_same_thread=False because FastAPI's TestClient dispatches
      requests on worker threads while the session was created in the
      main thread; the default sqlite driver refuses cross-thread use.
    - StaticPool for in-memory databases so every connection sees the
      same database (otherwise each new connection gets a fresh empty DB).

    On-disk sqlite (file:... or sqlite:///path.db) only needs the
    check_same_thread relaxation; the OS file backs cross-connection state.
    """
    if url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        # ":memory:" only lives inside a single connection. Force StaticPool
        # so the engine reuses one connection across the test process.
        is_memory = ":memory:" in url or url.endswith(":memory:")
        if is_memory:
            return create_engine(
                url,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        return create_engine(url, connect_args=connect_args)
    return create_engine(url)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
