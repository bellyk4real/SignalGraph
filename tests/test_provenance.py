import os

import pytest
from sqlalchemy import select, text

pytest.importorskip("psycopg")

from src.db import get_engine, get_session_factory  # noqa: E402
from src.graph.build_claims import build_official_document_claims, build_vendor_candidate_claims, ClaimBuildSummary  # noqa: E402
from src.graph.claims import ClaimPolicyError, accept_claim, attach_evidence, submit_claim  # noqa: E402
from src.graph.documents import chunk_text, create_source_document  # noqa: E402
from src.graph.models import Claim, ClaimStatus, DocumentChunk, EntityType  # noqa: E402
from src.ingestion import official_documents, synthetic_vendor  # noqa: E402
from src.resolution.matcher import get_or_create_entity, resolve_vendor_investors  # noqa: E402
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
def built_claims(db_session):
    synthetic_vendor.main()
    official_documents.main()
    validate_pending_raw_records(db_session)
    resolve_vendor_investors(db_session)

    summary = ClaimBuildSummary()
    build_vendor_candidate_claims(db_session, summary)
    build_official_document_claims(db_session, summary)
    db_session.commit()
    return summary


def test_chunk_text_splits_on_word_count():
    text_ = " ".join(f"word{i}" for i in range(250))
    chunks = chunk_text(text_, chunk_words=80)
    assert len(chunks) == 4
    assert chunks[0].split()[0] == "word0"


def test_vendor_funding_round_stays_candidate_never_accepted(built_claims, db_session):
    claim = db_session.scalars(
        select(Claim).where(Claim.claim_type == "funding_round", Claim.source_id == "vendor_enrichment")
    ).first()
    assert claim is not None
    assert claim.status == ClaimStatus.CANDIDATE


def test_official_announcement_produces_accepted_evidence_backed_claim(built_claims, db_session):
    claim = db_session.scalars(
        select(Claim).where(Claim.claim_type == "funding_round", Claim.source_id == "first_party_announcement")
    ).first()
    assert claim is not None
    assert claim.status == ClaimStatus.ACCEPTED
    assert claim.valid_until is not None  # freshness SLA applied


def test_thesis_claim_matches_readme_worked_example(built_claims, db_session):
    claim = db_session.scalars(select(Claim).where(Claim.claim_type == "thesis")).first()
    assert claim is not None
    assert claim.status == ClaimStatus.ACCEPTED
    assert "We lead Seed and Series A investments" in claim.claim_value["text"]


def test_accepted_claim_always_has_evidence(built_claims, db_session):
    accepted = db_session.scalars(select(Claim).where(Claim.status == ClaimStatus.ACCEPTED)).all()
    assert len(accepted) >= 2
    for claim in accepted:
        from src.graph.models import ClaimEvidence

        evidence_count = db_session.scalar(
            select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id).limit(1)
        )
        assert evidence_count is not None


def test_gdelt_source_cannot_create_accepted_claims(db_session):
    entity = get_or_create_entity(db_session, entity_type=EntityType.COMPANY, canonical_name="GDELT Test Co")
    claim = submit_claim(
        db_session,
        subject_entity_id=entity.id,
        claim_type="funding_round",
        claim_value={"headline": "GridFlow raises €4m seed round"},
        source_id="gdelt",
    )
    with pytest.raises(ClaimPolicyError):
        accept_claim(db_session, claim)


def test_accept_claim_requires_evidence(db_session):
    entity = get_or_create_entity(db_session, entity_type=EntityType.INVESTOR_FIRM, canonical_name="No Evidence Investor")
    claim = submit_claim(
        db_session,
        subject_entity_id=entity.id,
        claim_type="thesis",
        claim_value={"text": "unsupported assertion"},
        source_id="first_party_website",
    )
    with pytest.raises(ClaimPolicyError):
        accept_claim(db_session, claim)


def test_document_chunks_have_search_vector_and_embedding(built_claims, db_session):
    chunk = db_session.scalars(select(DocumentChunk)).first()
    assert chunk is not None
    assert chunk.embedding is not None
    assert len(chunk.embedding) == 128

    matches = db_session.execute(
        text("SELECT id FROM document_chunk WHERE search_vector @@ plainto_tsquery('english', :q)"),
        {"q": "Seed and Series A"},
    ).all()
    assert len(matches) >= 1
