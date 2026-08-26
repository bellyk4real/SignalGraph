import uuid

import pytest
import respx
from httpx import Response
from sqlalchemy import select

from src.ingestion import (
    gdelt_discovery,
    official_documents,
    synthetic_communications,
    synthetic_vendor,
)
from src.ingestion.base import UnregisteredSourceError, upsert_raw_record
from src.ingestion.companies_house import CompaniesHouseClient
from src.ingestion.models import RawRecord, SourceEvent
from src.validation.models import Quarantine
from src.validation.quality_gates import validate_pending_raw_records


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


def test_faulty_vendor_feed_quarantines_exactly_the_bad_rows(db_session):
    synthetic_vendor.main()
    validate_pending_raw_records(db_session)

    rows = db_session.scalars(select(RawRecord).where(RawRecord.record_type == "vendor_funding_round")).all()
    status_by_id = {row.raw_payload["vendor_round_id"]: row.validation_status for row in rows}

    assert status_by_id["R-001"] == "valid"
    assert status_by_id["R-002"] == "quarantined"
    assert status_by_id["R-003"] == "quarantined"
    assert status_by_id["R-004"] == "quarantined"

    reasons_by_round = {}
    for row in rows:
        if row.validation_status != "quarantined":
            continue
        reasons = db_session.scalars(select(Quarantine).where(Quarantine.raw_record_id == row.id)).all()
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

    count = db_session.scalar(select(RawRecord).where(RawRecord.source_id == "not_a_real_source"))
    assert count is None
