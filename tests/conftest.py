import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytest.importorskip("psycopg")

from src.db import get_engine, get_session_factory


def _db_reachable() -> bool:
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        get_engine().connect().close()
    except Exception:  # noqa: BLE001
        return False
    return True


@pytest.fixture(scope="session", autouse=True)
def _load_source_registry():
    """Every claim/entity fixture depends on source_registry rows existing
    (FK constraint). Loading it here makes the suite self-contained on a
    freshly migrated database (CI, a new contributor's machine) instead of
    silently depending on someone having run the loader manually first.
    """
    if not _db_reachable():
        return
    from src.ingestion.load_source_registry import load_registry_entries, upsert_source_registry

    session_factory = get_session_factory()
    with session_factory() as session:
        upsert_source_registry(session, load_registry_entries())


@pytest.fixture
def db_session():
    """Shared DB fixture for every DB-dependent test module. Skips cleanly
    (rather than failing) when DATABASE_URL isn't set or Postgres isn't
    reachable, so `uv run pytest` degrades gracefully without a running
    `docker compose up -d postgres`.
    """
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set; skipping DB-dependent test")
    try:
        get_engine().connect().close()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Postgres not reachable: {exc}")

    session_factory = get_session_factory()
    with session_factory() as session:
        yield session
        session.rollback()
