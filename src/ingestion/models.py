import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base, TimestampMixin, UUIDPKMixin


class SourceRegistry(Base):
    """Authority, claim policy, freshness, sensitivity, and retrieval
    eligibility for one ingestion source. The control plane every other
    pipeline stage checks before treating a record as evidence.
    """

    __tablename__ = "source_registry"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    source_name: Mapped[str] = mapped_column(String, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    authority_tier: Mapped[int] = mapped_column(Integer, nullable=False)
    permitted_claim_types: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    freshness_sla_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pii_classification: Mapped[str] = mapped_column(String, nullable=False)
    allowed_for_agent_retrieval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_create_accepted_claims: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    policy_note: Mapped[str] = mapped_column(String, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IngestionRun(UUIDPKMixin, TimestampMixin, Base):
    """Pipeline-run metrics, status, and error context for one connector invocation."""

    __tablename__ = "ingestion_run"

    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_quarantined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class RawRecord(UUIDPKMixin, TimestampMixin, Base):
    """Immutable raw structured payload preserved before any destructive transformation."""

    __tablename__ = "raw_record"

    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingestion_run.id"), nullable=False
    )
    record_type: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SourceEvent(UUIDPKMixin, TimestampMixin, Base):
    """Discovery/change event, including GDELT-style discovery findings.

    A discovery event never carries an accepted claim itself — see
    README "Core product principle": discovery is not evidence.
    """

    __tablename__ = "source_event"

    source_id: Mapped[str] = mapped_column(ForeignKey("source_registry.source_id"), nullable=False)
    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_record.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="discovered_only")
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
