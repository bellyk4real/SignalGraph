import os
import uuid

import pytest
from sqlalchemy import select

pytest.importorskip("psycopg")

from src.agent.schemas import InvestorCandidateRequest, InvestorEvidenceRequest, RelationshipMemoryRequest  # noqa: E402
from src.agent.tools import find_investor_candidates, get_investor_evidence, search_relationship_memory  # noqa: E402
from src.db import get_engine, get_session_factory  # noqa: E402
from src.graph.build_claims import ClaimBuildSummary, build_official_document_claims, build_vendor_candidate_claims  # noqa: E402
from src.graph.build_communications import build_communications  # noqa: E402
from src.graph.models import Entity, EntityType  # noqa: E402
from src.ingestion import official_documents, synthetic_communications, synthetic_vendor  # noqa: E402
from src.resolution.matcher import resolve_vendor_investors  # noqa: E402
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


@pytest.fixture
def full_pipeline(db_session):
    synthetic_vendor.main()
    synthetic_communications.main()
    official_documents.main()
    validate_pending_raw_records(db_session)
    resolve_vendor_investors(db_session)

    summary = ClaimBuildSummary()
    build_vendor_candidate_claims(db_session, summary)
    build_official_document_claims(db_session, summary)
    build_communications(db_session)
    db_session.commit()


def test_find_investor_candidates_returns_northstar_with_evidence(full_pipeline, db_session):
    response = find_investor_candidates(
        db_session,
        InvestorCandidateRequest(
            company_name="GridFlow GmbH",
            stage="seed",
            sectors=["climate"],
            geographies=["EU"],
            target_raise_eur=4_000_000,
        ),
    )
    assert response.insufficient_evidence is False
    names = {c.investor_name for c in response.candidates}
    assert "Northstar Ventures" in names

    northstar = next(c for c in response.candidates if c.investor_name == "Northstar Ventures")
    assert northstar.evidence
    assert all(e.excerpt for e in northstar.evidence)
    assert 0.0 <= northstar.fit_score <= 1.0
    assert northstar.caveats  # honest about neutral sector/geo/cheque-size scoring


def test_get_investor_evidence_links_investor_to_company_funding(full_pipeline, db_session):
    northstar = db_session.scalars(
        select(Entity).where(Entity.entity_type == EntityType.INVESTOR_FIRM, Entity.canonical_name == "Northstar Ventures")
    ).first()
    gridflow = db_session.scalars(
        select(Entity).where(Entity.entity_type == EntityType.COMPANY, Entity.canonical_name == "GridFlow GmbH")
    ).first()

    evidence = get_investor_evidence(
        db_session, InvestorEvidenceRequest(investor_id=northstar.id, company_id=gridflow.id)
    )
    assert evidence
    assert any("GridFlow" in e.excerpt for e in evidence)


def test_search_relationship_memory_respects_sensitivity(full_pipeline, db_session):
    gridflow = db_session.scalars(
        select(Entity).where(Entity.entity_type == EntityType.COMPANY, Entity.canonical_name == "GridFlow GmbH")
    ).first()

    public_response = search_relationship_memory(
        db_session,
        RelationshipMemoryRequest(entity_id=gridflow.id, query="warm introduction Northstar", allowed_sensitivity="public"),
    )
    assert public_response.insufficient_evidence is True

    restricted_response = search_relationship_memory(
        db_session,
        RelationshipMemoryRequest(
            entity_id=gridflow.id, query="warm introduction Northstar", allowed_sensitivity="restricted"
        ),
    )
    assert restricted_response.insufficient_evidence is False
    assert any("warm introduction" in r.text for r in restricted_response.results)


def test_search_relationship_memory_insufficient_evidence_for_unknown_entity(db_session):
    response = search_relationship_memory(
        db_session,
        RelationshipMemoryRequest(entity_id=uuid.uuid4(), query="anything", allowed_sensitivity="restricted"),
    )
    assert response.insufficient_evidence is True
    assert response.results == []
