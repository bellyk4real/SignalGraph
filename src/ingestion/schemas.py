from typing import Literal

from pydantic import BaseModel, Field

PiiClassification = Literal["public", "internal", "restricted"]


class SourceRegistryEntry(BaseModel):
    """Typed contract for one row of data/source_registry.yml.

    See README "Source policy" for the field semantics and the worked
    companies_house example this schema is modeled on.
    """

    source_id: str
    source_name: str
    source_type: str
    authority_tier: int = Field(ge=1, le=5)
    permitted_claim_types: list[str] = Field(default_factory=list)
    freshness_sla_hours: int | None = None
    pii_classification: PiiClassification
    allowed_for_agent_retrieval: bool
    requires_human_review: bool = False
    can_create_accepted_claims: bool = False
    policy_note: str = ""
