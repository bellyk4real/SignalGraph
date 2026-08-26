import os
import uuid

import pytest
from sqlalchemy import select

pytest.importorskip("psycopg")

from src.db import get_engine, get_session_factory  # noqa: E402
from src.ingestion import synthetic_vendor  # noqa: E402
from src.ingestion.base import UnregisteredSourceError, upsert_raw_record  # noqa: E402
from src.ingestion.models import RawRecord  # noqa: E402
from src.validation.models import Quarantine  # noqa: E402
from src.validation.quality_gates import validate_pending_raw_records  # noqa: E402


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


def test_faulty_vendor_feed_quarantines_exactly_the_bad_rows(db_session):
    synthetic_vendor.main()
    validate_pending_raw_records(db_session)

    rows = db_session.scalars(
        select(RawRecord).where(RawRecord.record_type == "vendor_funding_round")
    ).all()
    status_by_id = {row.raw_payload["vendor_round_id"]: row.validation_status for row in rows}

    assert status_by_id["R-001"] == "valid"
    assert status_by_id["R-002"] == "quarantined"
    assert status_by_id["R-003"] == "quarantined"
    assert status_by_id["R-004"] == "quarantined"

    reasons_by_round = {}
    for row in rows:
        if row.validation_status != "quarantined":
            continue
        reasons = db_session.scalars(
            select(Quarantine).where(Quarantine.raw_record_id == row.id)
        ).all()
        reasons_by_round[row.raw_payload["vendor_round_id"]] = {r.reason_code for r in reasons}

    assert reasons_by_round["R-002"] == {"invalid_date"}
    assert reasons_by_round["R-003"] == {"negative_amount"}
    assert reasons_by_round["R-004"] == {"invalid_currency"}


def test_unregistered_source_is_rejected_before_writing_a_raw_record(db_session):
    with pytest.raises(UnregisteredSourceError):
        upsert_raw_record(
            db_session,
            source_id="not_a_real_source",
            ingestion_run_id=uuid.uuid4(),
            record_type="vendor_funding_round",
            payload={"anything": "goes"},
        )
    db_session.rollback()

    count = db_session.scalar(
        select(RawRecord).where(RawRecord.source_id == "not_a_real_source")
    )
    assert count is None
