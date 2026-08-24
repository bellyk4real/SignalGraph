import os

import pytest
import respx
from httpx import Response
from sqlalchemy import select

pytest.importorskip("psycopg")

from src.db import get_engine, get_session_factory  # noqa: E402
from src.ingestion import gdelt_discovery, official_documents, synthetic_communications, synthetic_vendor  # noqa: E402
from src.ingestion.companies_house import CompaniesHouseClient  # noqa: E402
from src.ingestion.models import RawRecord, SourceEvent  # noqa: E402


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


def _raw_record_count(session, source_id: str) -> int:
    return len(session.scalars(select(RawRecord).where(RawRecord.source_id == source_id)).all())


def test_synthetic_vendor_ingestion_is_idempotent(db_session):
    synthetic_vendor.main()
    synthetic_vendor.main()
    count = _raw_record_count(db_session, synthetic_vendor.SOURCE_ID)
    # 4 funding rounds + 3 investors, each run exactly once despite two calls
    assert count == 7


def test_synthetic_vendor_preserves_invalid_rows_as_raw(db_session):
    synthetic_vendor.main()
    rows = db_session.scalars(
        select(RawRecord).where(
            RawRecord.source_id == synthetic_vendor.SOURCE_ID,
            RawRecord.record_type == "vendor_funding_round",
        )
    ).all()
    payloads = {row.raw_payload["vendor_round_id"]: row.raw_payload for row in rows}
    assert payloads["R-002"]["announced_on"] == "2026-15-48"
    assert payloads["R-003"]["amount"] == "-250000"
    assert payloads["R-004"]["currency"] == "EURO"


def test_synthetic_communications_ingestion_is_idempotent(db_session):
    synthetic_communications.main()
    synthetic_communications.main()
    assert _raw_record_count(db_session, synthetic_communications.SOURCE_ID) == 2


def test_official_documents_ingestion_is_idempotent(db_session):
    official_documents.main()
    official_documents.main()
    assert _raw_record_count(db_session, "first_party_website") == 1
    assert _raw_record_count(db_session, "first_party_announcement") == 1


def test_gdelt_discovery_creates_event_only_no_raw_record(db_session):
    gdelt_discovery.main()

    events = db_session.scalars(select(SourceEvent).where(SourceEvent.source_id == "gdelt")).all()
    assert len(events) == 1
    assert events[0].status == "discovered_only"
    assert _raw_record_count(db_session, "gdelt") == 0


def test_companies_house_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
    from src.settings import get_settings

    get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        CompaniesHouseClient(api_key=None)


@respx.mock
def test_companies_house_client_parses_mocked_profile():
    respx.get("https://api.company-information.service.gov.uk/company/12345678").mock(
        return_value=Response(
            200,
            json={
                "company_number": "12345678",
                "company_name": "GRIDFLOW LTD",
                "company_status": "active",
                "date_of_creation": "2024-01-01",
            },
        )
    )
    with CompaniesHouseClient(api_key="test-key") as client:
        profile = client.get_company_profile("12345678")

    assert profile.company_name == "GRIDFLOW LTD"
    assert profile.company_status == "active"
