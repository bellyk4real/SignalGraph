import os

import pytest
from dotenv import load_dotenv

load_dotenv()

pytest.importorskip("psycopg")

from src.db import get_engine, get_session_factory


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
