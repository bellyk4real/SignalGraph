"""Claim lifecycle enforcement tied to source policy — see README's "Claim
and provenance model" and "Core quality gates". A claim starts as a
candidate; it can only become accepted (and therefore agent-visible) if its
source is registered, permits the claim type, is authorized to create
accepted claims, and the claim has at least one evidence link.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from src.graph.models import Claim, ClaimEvidence, ClaimStatus, SourceDocument
from src.ingestion.models import SourceRegistry


class ClaimPolicyError(Exception):
    """Raised when a claim cannot be accepted under its source's policy."""


def submit_claim(
    session: Session,
    *,
    subject_entity_id,
    claim_type: str,
    claim_value: dict,
    source_id: str,
    confidence: float = 0.0,
    entity_relationship_id=None,
    raw_record_id=None,
) -> Claim:
    """Creates a candidate claim. Candidate claims are never agent-visible —
    see accept_claim for the promotion path.
    """
    claim = Claim(
        subject_entity_id=subject_entity_id,
        entity_relationship_id=entity_relationship_id,
        raw_record_id=raw_record_id,
        claim_type=claim_type,
        claim_value=claim_value,
        status=ClaimStatus.CANDIDATE,
        source_id=source_id,
        confidence=confidence,
    )
    session.add(claim)
    session.flush()
    return claim


def attach_evidence(
    session: Session,
    claim: Claim,
    *,
    source_document: SourceDocument,
    text_span: str,
    document_chunk_id=None,
    span_start: int | None = None,
    span_end: int | None = None,
) -> ClaimEvidence:
    evidence = ClaimEvidence(
        claim_id=claim.id,
        source_document_id=source_document.id,
        document_chunk_id=document_chunk_id,
        text_span=text_span,
        span_start=span_start,
        span_end=span_end,
    )
    session.add(evidence)
    session.flush()
    return evidence


def accept_claim(session: Session, claim: Claim) -> Claim:
    """Promotes a candidate claim to accepted, enforcing every quality gate
    in README's table that applies at acceptance time:
      - source must be registered and permit this claim_type
      - source must be authorized to create accepted claims
      - the claim must have at least one evidence link
    Sets valid_until from the source's freshness SLA so a stale claim
    naturally falls out of the agent-visible window without special-casing
    retrieval logic.
    """
    source = session.get(SourceRegistry, claim.source_id)
    if source is None:
        raise ClaimPolicyError(f"claim {claim.id}: source_id {claim.source_id!r} is not registered")

    if not source.can_create_accepted_claims:
        raise ClaimPolicyError(
            f"claim {claim.id}: source {claim.source_id!r} is not authorized to create accepted claims "
            f"({source.policy_note})"
        )

    if claim.claim_type not in source.permitted_claim_types:
        raise ClaimPolicyError(
            f"claim {claim.id}: claim_type {claim.claim_type!r} is not permitted for source {claim.source_id!r}"
        )

    has_evidence = (
        session.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).first() is not None
    )
    if not has_evidence:
        raise ClaimPolicyError(f"claim {claim.id}: accepted claims must have at least one evidence link")

    now = datetime.now(UTC)
    claim.status = ClaimStatus.ACCEPTED
    claim.valid_from = now
    claim.valid_until = now + timedelta(hours=source.freshness_sla_hours) if source.freshness_sla_hours else None
    session.flush()
    return claim
