from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


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
