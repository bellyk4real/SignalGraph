"""The three agent tools from the README's "Agent tools" section:
find_investor_candidates, get_investor_evidence, search_relationship_memory.
Every result carries evidence and uncertainty; when minimum evidence is
unavailable, tools return the insufficient_evidence shape instead of a
best-effort guess.
"""

from sqlalchemy.orm import Session

from src.agent.schemas import (
    EvidenceReference,
    InvestorCandidateRequest,
    InvestorCandidateResponse,
    InvestorEvidenceRequest,
    RelationshipMemoryRequest,
    RelationshipMemoryResponse,
    RelationshipMemoryResult,
)
from src.retrieval.hybrid import find_investor_candidates as _find_investor_candidates
from src.retrieval.hybrid import get_investor_evidence as _get_investor_evidence
from src.retrieval.hybrid import search_relationship_memory as _search_relationship_memory


def find_investor_candidates(session: Session, request: InvestorCandidateRequest) -> InvestorCandidateResponse:
    candidates = _find_investor_candidates(
        session,
        stage=request.stage,
        max_results=request.max_results,
        allowed_sensitivity=request.allowed_sensitivity,
    )
    session.commit()  # persist any audit_log rows written while assembling evidence
    if not candidates:
        return InvestorCandidateResponse(
            candidates=[],
            insufficient_evidence=True,
            retrieval_notes=["No accepted, sufficiently recent evidence supports a qualifying investor match."],
        )
    return InvestorCandidateResponse(candidates=candidates)


def get_investor_evidence(session: Session, request: InvestorEvidenceRequest) -> list[EvidenceReference]:
    result = _get_investor_evidence(
        session,
        investor_id=request.investor_id,
        company_id=request.company_id,
        allowed_sensitivity=request.allowed_sensitivity,
    )
    session.commit()  # persist audit_log rows
    return result


def search_relationship_memory(session: Session, request: RelationshipMemoryRequest) -> RelationshipMemoryResponse:
    scored = _search_relationship_memory(
        session,
        entity_id=request.entity_id,
        query=request.query,
        allowed_sensitivity=request.allowed_sensitivity,
        max_results=request.max_results,
    )
    session.commit()  # persist audit_log rows
    if not scored:
        return RelationshipMemoryResponse(
            results=[],
            insufficient_evidence=True,
            retrieval_notes=["No permitted communications found for this entity and permission level."],
        )

    results = [
        RelationshipMemoryResult(
            communication_id=comm.id,
            text=comm.raw_text if request.allowed_sensitivity == "restricted" else comm.redacted_text,
            sensitivity=comm.sensitivity.value,
            occurred_at=comm.occurred_at,
            relevance_score=round(score, 4),
        )
        for comm, score in scored
    ]
    return RelationshipMemoryResponse(results=results)
