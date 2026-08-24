"""Canonical operational knowledge graph: entities, identifiers, relationships,
funding rounds, entity-resolution decisions, claims/evidence, documents, and
communications. See README "Data model" and "Claim and provenance model".
"""

import enum
import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base, TimestampMixin, UUIDPKMixin
from src.enrichment.embeddings import EMBEDDING_DIM


def pg_enum(py_enum: type[enum.StrEnum], name: str) -> Enum:
    """Enum(py_enum) persists the Python member *name* by default (e.g.
    "CANDIDATE"), not its lowercase `.value` ("candidate") — values_callable
    makes the native Postgres enum use `.value`, matching the vocabulary
    documented in the README (README's claim status lifecycle, canonical
    entity types, etc. are all lowercase).
    """
    return Enum(py_enum, name=name, values_callable=lambda e: [member.value for member in e])


class EntityType(enum.StrEnum):
    COMPANY = "company"
    INVESTOR_FIRM = "investor_firm"
    PERSON = "person"
    FUND = "fund"


class ResolutionDecisionType(enum.StrEnum):
    MATCH = "match"
    NO_MATCH = "no_match"
    NEEDS_REVIEW = "needs_review"


class ClaimStatus(enum.StrEnum):
    CANDIDATE = "candidate"
    ACCEPTED = "accepted"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class Sensitivity(enum.StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    RESTRICTED = "restricted"


class Entity(UUIDPKMixin, TimestampMixin, Base):
    """Canonical graph node: a company, investor firm, person, or fund."""

    __tablename__ = "entity"

    entity_type: Mapped[EntityType] = mapped_column(pg_enum(EntityType, "entity_type"), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False, index=True)


class EntityIdentifier(UUIDPKMixin, TimestampMixin, Base):
    """A source ID, domain, registry number, or alias attached to an entity.

    See README "Match tiers" — identifier_type/identifier_value pairs are the
    evidence entity resolution matches on (e.g. companies_house_number, domain).
    """

    __tablename__ = "entity_identifier"

    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)
    identifier_type: Mapped[str] = mapped_column(String, nullable=False)
    identifier_value: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("source_registry.source_id"), nullable=True)
    verified: Mapped[bool] = mapped_column(default=False)


class EntityResolutionDecision(UUIDPKMixin, TimestampMixin, Base):
    """Explainable, versioned, reversible entity-matching outcome.

    Identity resolution is a governed decision, not a destructive dedup step —
    see README "Entity resolution". `matched_entity_id` is null for a
    no_match/needs_review decision.
    """

    __tablename__ = "entity_resolution_decision"

    subject_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)
    matched_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity.id"), nullable=True
    )
    decision: Mapped[ResolutionDecisionType] = mapped_column(
        pg_enum(ResolutionDecisionType, "resolution_decision_type"), nullable=False
    )
    match_score: Mapped[float] = mapped_column(nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rule_version: Mapped[str] = mapped_column(String, nullable=False)
    reviewer: Mapped[str] = mapped_column(String, nullable=False, default="system")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reversal_reason: Mapped[str | None] = mapped_column(String, nullable=True)


class FundingRound(UUIDPKMixin, TimestampMixin, Base):
    """A funding round is a first-class event, not a flat investor/company field.

    See README "Funding rounds are first-class".
    """

    __tablename__ = "funding_round"

    company_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)
    round_type: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    announced_on: Mapped[date | None] = mapped_column(nullable=True)

    __table_args__ = (CheckConstraint("amount IS NULL OR amount >= 0", name="ck_funding_round_amount_non_negative"),)


class EntityRelationship(UUIDPKMixin, TimestampMixin, Base):
    """An effective-dated typed graph edge from one entity to either another
    entity or a funding round (never both) — README's relationship examples:
    Investor--participated_in/led-->Funding Round,
    Investor--portfolio_company_of-->Company, Person--partner_at-->Investor,
    Person--founder_of-->Company, Person--introduced_by-->Person.
    """

    __tablename__ = "entity_relationship"

    from_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String, nullable=False)
    to_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity.id"), nullable=True
    )
    to_funding_round_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("funding_round.id"), nullable=True
    )
    effective_from: Mapped[date | None] = mapped_column(nullable=True)
    effective_to: Mapped[date | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(to_entity_id IS NOT NULL)::int + (to_funding_round_id IS NOT NULL)::int = 1",
            name="ck_entity_relationship_single_target",
        ),
    )


class SourceDocument(UUIDPKMixin, TimestampMixin, Base):
    """Raw/parsed document backing claim evidence, with content hash and sensitivity."""

    __tablename__ = "source_document"

    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_record.id"), nullable=True
    )
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sensitivity: Mapped[Sensitivity] = mapped_column(
        pg_enum(Sensitivity, "sensitivity"), nullable=False, default=Sensitivity.PUBLIC
    )
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Claim(UUIDPKMixin, TimestampMixin, Base):
    """A candidate/accepted/disputed/superseded/rejected factual assertion.

    Business facts are never overwritten directly onto an entity — see
    README "Claim and provenance model" and ADR-002.
    """

    __tablename__ = "claim"

    subject_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)
    entity_relationship_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entity_relationship.id"), nullable=True
    )
    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_record.id"), nullable=True
    )
    claim_type: Mapped[str] = mapped_column(String, nullable=False)
    claim_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[ClaimStatus] = mapped_column(
        pg_enum(ClaimStatus, "claim_status"), nullable=False, default=ClaimStatus.CANDIDATE
    )
    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_by_claim_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("claim.id"), nullable=True
    )


class DocumentChunk(UUIDPKMixin, TimestampMixin, Base):
    """A full-text/vector-searchable segment of a source_document.

    `search_vector` is a Postgres-generated column (no app-side sync needed);
    `embedding` is populated by src.enrichment.embeddings at chunk-creation
    time. Hybrid retrieval (Sprint 9) combines both with SQL filters and
    graph traversal.
    """

    __tablename__ = "document_chunk"

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', chunk_text)", persisted=True), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    __table_args__ = (Index("ix_document_chunk_search_vector", "search_vector", postgresql_using="gin"),)


class ClaimEvidence(UUIDPKMixin, TimestampMixin, Base):
    """Links a claim to the document/chunk and exact text span that supports it."""

    __tablename__ = "claim_evidence"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claim.id"), nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_document.id"), nullable=False
    )
    document_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document_chunk.id"), nullable=True
    )
    text_span: Mapped[str] = mapped_column(Text, nullable=False)
    span_start: Mapped[int | None] = mapped_column(nullable=True)
    span_end: Mapped[int | None] = mapped_column(nullable=True)


class Communication(UUIDPKMixin, TimestampMixin, Base):
    """Restricted email/call memory representation.

    Raw communications are kept separate from the redacted/searchable
    representation — see README "Security and communications".
    """

    __tablename__ = "communication"

    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_record.id"), nullable=True
    )
    communication_type: Mapped[str] = mapped_column(String, nullable=False)
    sensitivity: Mapped[Sensitivity] = mapped_column(
        pg_enum(Sensitivity, "sensitivity"), nullable=False, default=Sensitivity.RESTRICTED
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    redacted_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class CommunicationParticipant(UUIDPKMixin, TimestampMixin, Base):
    """Join table: a communication involves a person/company/investor entity."""

    __tablename__ = "communication_participant"

    communication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communication.id"), nullable=False
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entity.id"), nullable=False)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
