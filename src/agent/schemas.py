"""Agent tool contracts, verbatim from the README's "Agent tools" and
"Agent response contract" sections.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class InvestorCandidateRequest(BaseModel):
    company_id: UUID | None = None
    company_name: str
    stage: str
    sectors: list[str]
    geographies: list[str]
    target_raise_eur: int | None = None
    max_results: int = 10
    allowed_sensitivity: str = "public"


class InvestorEvidenceRequest(BaseModel):
    investor_id: UUID
    company_id: UUID
    allowed_sensitivity: str = "public"


class RelationshipMemoryRequest(BaseModel):
    entity_id: UUID
    query: str
    allowed_sensitivity: str = "public"
    max_results: int = 10


class EvidenceReference(BaseModel):
    claim_id: UUID | None
    document_id: UUID
    chunk_id: UUID | None
    source_id: str
    source_url: str | None
    excerpt: str
    authority_tier: int
    published_at: datetime | None
    retrieved_at: datetime
    confidence: float


class InvestorCandidate(BaseModel):
    investor_id: UUID
    investor_name: str
    fit_score: float
    rationale: list[str]
    caveats: list[str]
    evidence: list[EvidenceReference]
    data_freshness: datetime


class InvestorCandidateResponse(BaseModel):
    candidates: list[InvestorCandidate]
    insufficient_evidence: bool = False
    retrieval_notes: list[str] = []


class RelationshipMemoryResult(BaseModel):
    communication_id: UUID
    text: str
    sensitivity: str
    occurred_at: datetime
    relevance_score: float


class RelationshipMemoryResponse(BaseModel):
    results: list[RelationshipMemoryResult]
    insufficient_evidence: bool = False
    retrieval_notes: list[str] = []
