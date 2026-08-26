import pytest
from sqlalchemy import select

from src.agent.models import AuditLog
from src.agent.schemas import InvestorEvidenceRequest, RelationshipMemoryRequest
from src.agent.tools import get_investor_evidence, search_relationship_memory
from src.graph.build_claims import (
    ClaimBuildSummary,
    build_official_document_claims,
    build_vendor_candidate_claims,
)
from src.graph.build_communications import build_communications
from src.graph.claims import ClaimPolicyError, accept_claim, attach_evidence, submit_claim
from src.graph.documents import create_source_document
from src.graph.models import Entity, EntityType, Sensitivity
from src.ingestion import official_documents, synthetic_communications, synthetic_vendor
from src.resolution.matcher import get_or_create_entity, resolve_vendor_investors
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


def test_opensanctions_cannot_create_accepted_claims(db_session):
    entity = get_or_create_entity(db_session, entity_type=EntityType.COMPANY, canonical_name="Screening Test Co")
    claim = submit_claim(
        db_session,
        subject_entity_id=entity.id,
        claim_type="screening_match",
        claim_value={"list": "sanctions-fixture", "match": "possible"},
        source_id="opensanctions",
    )
    with pytest.raises(ClaimPolicyError):
        accept_claim(db_session, claim)


def test_restricted_evidence_document_excluded_at_public_but_allowed_at_restricted(db_session):
    investor = get_or_create_entity(db_session, entity_type=EntityType.INVESTOR_FIRM, canonical_name="Restricted Doc Investor")
    company = get_or_create_entity(db_session, entity_type=EntityType.COMPANY, canonical_name="Restricted Doc Company")

    document = create_source_document(
        db_session,
        source_id="synthetic_communications",
        full_text="Internal relationship note: strong prior working relationship.",
        sensitivity=Sensitivity.RESTRICTED,
    )
    claim = submit_claim(
        db_session,
        subject_entity_id=investor.id,
        claim_type="relationship_context",
        claim_value={"note": "strong prior working relationship"},
        source_id="synthetic_communications",
    )
    attach_evidence(db_session, claim, source_document=document, text_span="strong prior working relationship")
    accept_claim(db_session, claim)
    db_session.commit()

    public_evidence = get_investor_evidence(
        db_session, InvestorEvidenceRequest(investor_id=investor.id, company_id=company.id, allowed_sensitivity="public")
    )
    assert all(e.claim_id != claim.id for e in public_evidence)

    restricted_evidence = get_investor_evidence(
        db_session,
        InvestorEvidenceRequest(investor_id=investor.id, company_id=company.id, allowed_sensitivity="restricted"),
    )
    assert any(e.claim_id == claim.id for e in restricted_evidence)

    denied = db_session.scalars(
        select(AuditLog).where(
            AuditLog.subject_id == document.id, AuditLog.decision == "denied", AuditLog.requested_sensitivity == "public"
        )
    ).first()
    allowed = db_session.scalars(
        select(AuditLog).where(
            AuditLog.subject_id == document.id, AuditLog.decision == "allowed", AuditLog.requested_sensitivity == "restricted"
        )
    ).first()
    assert denied is not None
    assert allowed is not None


def test_search_relationship_memory_denial_is_audited(full_pipeline, db_session):
    gridflow = db_session.scalars(
        select(Entity).where(Entity.entity_type == EntityType.COMPANY, Entity.canonical_name == "GridFlow GmbH")
    ).first()

    search_relationship_memory(
        db_session,
        RelationshipMemoryRequest(entity_id=gridflow.id, query="warm introduction", allowed_sensitivity="public"),
    )

    denied = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "search_relationship_memory",
            AuditLog.decision == "denied",
            AuditLog.requested_sensitivity == "public",
        )
    ).all()
    assert len(denied) >= 1
    assert any(entry.resource_sensitivity == "restricted" for entry in denied)
