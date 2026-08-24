"""Hybrid retrieval: structured SQL filters + graph traversal + evidence
assembly backing the three agent tools in src/agent/tools.py.

Scope note: the demo fixture set has no structured sector/geography/
cheque-size claims for investors (only a free-text thesis claim), so those
ranking components are neutral (0.5) with an explicit caveat rather than a
fabricated score — see README's core principle: don't claim evidence that
doesn't exist. stage_fit is derived from keyword matching against accepted
claim text, and portfolio_similarity is a coarse "has done a deal before"
proxy via entity_relationship. This is honest about current fixture
coverage, not a claim of production-grade signal extraction.
"""

import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agent.schemas import EvidenceReference, InvestorCandidate
from src.enrichment.embeddings import get_embedding_provider
from src.graph.models import (
    Claim,
    ClaimEvidence,
    ClaimStatus,
    Communication,
    CommunicationParticipant,
    Entity,
    EntityRelationship,
    EntityType,
    SourceDocument,
)
from src.ingestion.models import SourceRegistry
from src.retrieval.ranking import candidate_score

SENSITIVITY_RANK = {"public": 0, "internal": 1, "restricted": 2}


def authority_score(tier: int) -> float:
    return max(0.0, (6 - tier) / 5)


def _is_fresh(claim: Claim) -> bool:
    return claim.valid_until is None or claim.valid_until > datetime.now(UTC)


def _accepted_agent_visible_claims(session: Session, subject_entity_id) -> list[Claim]:
    """README: "Only claims that are accepted, evidence-backed, permitted by
    source policy, non-expired-by-default-caveat, and authorised for the
    calling context are visible to agents." Evidence-backed and permitted
    are already enforced at accept_claim() time; this adds the
    allowed_for_agent_retrieval source check.
    """
    claims = session.scalars(
        select(Claim).where(Claim.subject_entity_id == subject_entity_id, Claim.status == ClaimStatus.ACCEPTED)
    ).all()
    visible = []
    for claim in claims:
        source = session.get(SourceRegistry, claim.source_id)
        if source is not None and source.allowed_for_agent_retrieval:
            visible.append(claim)
    return visible


def _evidence_for_claim(session: Session, claim: Claim, allowed_sensitivity: str) -> list[EvidenceReference]:
    allowed_rank = SENSITIVITY_RANK.get(allowed_sensitivity, 0)
    refs = []
    for evidence in session.scalars(select(ClaimEvidence).where(ClaimEvidence.claim_id == claim.id)).all():
        document = session.get(SourceDocument, evidence.source_document_id)
        if document is None or SENSITIVITY_RANK.get(document.sensitivity.value, 0) > allowed_rank:
            continue
        refs.append(
            EvidenceReference(
                claim_id=claim.id,
                document_id=document.id,
                chunk_id=evidence.document_chunk_id,
                source_id=document.source_id,
                source_url=document.url,
                excerpt=evidence.text_span,
                authority_tier=_authority_tier(session, document.source_id),
                published_at=document.published_at,
                retrieved_at=document.retrieved_at,
                confidence=claim.confidence,
            )
        )
    return refs


def _authority_tier(session: Session, source_id: str) -> int:
    source = session.get(SourceRegistry, source_id)
    return source.authority_tier if source is not None else 5


def score_investor(
    session: Session, investor: Entity, stage: str, allowed_sensitivity: str
) -> tuple[float, list[str], list[str], list[EvidenceReference], datetime | None] | None:
    claims = _accepted_agent_visible_claims(session, investor.id)
    if not claims:
        return None

    all_evidence: list[EvidenceReference] = []
    for claim in claims:
        all_evidence.extend(_evidence_for_claim(session, claim, allowed_sensitivity))
    if not all_evidence:
        return None

    thesis_text = " ".join(
        str(c.claim_value.get("text", "")) for c in claims if c.claim_type == "thesis"
    ).lower()
    stage_fit = 1.0 if stage.lower() in thesis_text else 0.4

    has_prior_deal = (
        session.scalars(
            select(EntityRelationship).where(
                EntityRelationship.from_entity_id == investor.id,
                EntityRelationship.relationship_type == "portfolio_company_of",
            )
        ).first()
        is not None
    )
    portfolio_similarity = 1.0 if has_prior_deal else 0.3

    tiers = [_authority_tier(session, c.source_id) for c in claims]
    source_authority_score = sum(authority_score(t) for t in tiers) / len(tiers)

    evidence_quality = sum(c.confidence for c in claims) / len(claims)
    freshness_score = sum(1.0 for c in claims if _is_fresh(c)) / len(claims)

    components = {
        "stage_fit": stage_fit,
        "sector_fit": 0.5,
        "geography_fit": 0.5,
        "cheque_size_fit": 0.5,
        "portfolio_similarity": portfolio_similarity,
        "source_authority_score": source_authority_score,
        "evidence_quality": evidence_quality,
        "freshness_score": freshness_score,
    }
    fit_score = candidate_score(components)

    rationale = [f"{len(claims)} accepted, evidence-backed claim(s) support this investor."]
    if stage_fit == 1.0:
        rationale.append(f"Accepted thesis explicitly mentions {stage!r}.")
    if has_prior_deal:
        rationale.append("Investor has at least one existing portfolio relationship on record.")

    caveats = [
        "No structured sector/geography/cheque-size evidence in the current data; those factors were scored neutral."
    ]
    if freshness_score < 1.0:
        caveats.append("At least one supporting claim has exceeded its source's freshness SLA.")

    data_freshness = max((e.retrieved_at for e in all_evidence), default=None)
    return fit_score, rationale, caveats, all_evidence, data_freshness


def find_investor_candidates(
    session: Session, *, stage: str, max_results: int, allowed_sensitivity: str
) -> list[InvestorCandidate]:
    investors = session.scalars(select(Entity).where(Entity.entity_type == EntityType.INVESTOR_FIRM)).all()

    candidates = []
    for investor in investors:
        result = score_investor(session, investor, stage, allowed_sensitivity)
        if result is None:
            continue
        fit_score, rationale, caveats, evidence, data_freshness = result
        candidates.append(
            InvestorCandidate(
                investor_id=investor.id,
                investor_name=investor.canonical_name,
                fit_score=round(fit_score, 4),
                rationale=rationale,
                caveats=caveats,
                evidence=evidence,
                data_freshness=data_freshness or datetime.now(UTC),
            )
        )

    candidates.sort(key=lambda c: c.fit_score, reverse=True)
    return candidates[:max_results]


def get_investor_evidence(
    session: Session, *, investor_id, company_id, allowed_sensitivity: str
) -> list[EvidenceReference]:
    refs: list[EvidenceReference] = []

    for claim in _accepted_agent_visible_claims(session, investor_id):
        refs.extend(_evidence_for_claim(session, claim, allowed_sensitivity))

    # Funding-round claims about the company, corroborated by an
    # investor->funding_round edge (led/participated_in) — graph traversal
    # linking the investor to this specific company's funding history.
    investor_edges = session.scalars(
        select(EntityRelationship).where(
            EntityRelationship.from_entity_id == investor_id,
            EntityRelationship.relationship_type.in_(["led", "participated_in"]),
        )
    ).all()
    funding_round_ids = {e.to_funding_round_id for e in investor_edges if e.to_funding_round_id is not None}

    for claim in _accepted_agent_visible_claims(session, company_id):
        if claim.claim_type == "funding_round" and funding_round_ids:
            refs.extend(_evidence_for_claim(session, claim, allowed_sensitivity))

    return refs


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def search_relationship_memory(
    session: Session, *, entity_id, query: str, allowed_sensitivity: str, max_results: int
) -> list[tuple[Communication, float]]:
    allowed_rank = SENSITIVITY_RANK.get(allowed_sensitivity, 0)

    communication_ids = session.scalars(
        select(CommunicationParticipant.communication_id).where(CommunicationParticipant.entity_id == entity_id)
    ).all()
    if not communication_ids:
        return []

    communications = session.scalars(
        select(Communication).where(Communication.id.in_(communication_ids))
    ).all()
    permitted = [c for c in communications if SENSITIVITY_RANK.get(c.sensitivity.value, 2) <= allowed_rank]
    if not permitted:
        return []

    provider = get_embedding_provider()
    query_vector = provider.embed(query)

    scored = []
    for comm in permitted:
        text = comm.raw_text if allowed_sensitivity == "restricted" else comm.redacted_text
        similarity = _cosine_similarity(query_vector, provider.embed(text or ""))
        scored.append((comm, similarity))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:max_results]
