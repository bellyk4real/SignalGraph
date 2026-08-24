import os

import pytest
from sqlalchemy import select

pytest.importorskip("psycopg")

from src.db import get_engine, get_session_factory  # noqa: E402
from src.ingestion.load_source_registry import load_registry_entries, upsert_source_registry  # noqa: E402
from src.ingestion.models import SourceRegistry  # noqa: E402


@pytest.fixture
def db_session():
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


def test_load_registry_entries_parses_all_source_classes():
    entries = load_registry_entries()
    ids = {entry.source_id for entry in entries}
    assert "companies_house" in ids
    assert "gdelt" in ids
    assert "synthetic_communications" in ids
    assert len(entries) == len(ids)


def test_upsert_is_idempotent(db_session):
    entries = load_registry_entries()

    first_count = upsert_source_registry(db_session, entries)
    second_count = upsert_source_registry(db_session, entries)

    rows = db_session.scalars(select(SourceRegistry)).all()
    assert first_count == second_count == len(entries)
    assert len(rows) == len(entries)
    assert {row.source_id for row in rows} == {e.source_id for e in entries}


def test_gdelt_cannot_create_accepted_claims():
    entries = {e.source_id: e for e in load_registry_entries()}
    assert entries["gdelt"].can_create_accepted_claims is False
    assert entries["gdelt"].allowed_for_agent_retrieval is False
