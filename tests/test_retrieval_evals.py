import uuid

import pytest
from sqlalchemy import select

from src.agent.schemas import (
    InvestorCandidateRequest,
    InvestorEvidenceRequest,
    RelationshipMemoryRequest,
)
from src.agent.tools import (
    find_investor_candidates,
    get_investor_evidence,
    search_relationship_memory,
)
from src.graph.build_claims import (
    ClaimBuildSummary,
    build_official_document_claims,
    build_vendor_candidate_claims,
)
from src.graph.build_communications import build_communications
from src.graph.models import Entity, EntityType
from src.ingestion import official_documents, synthetic_communications, synthetic_vendor
from src.resolution.matcher import resolve_vendor_investors
from src.validation.quality_gates import validate_pending_raw_records


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
