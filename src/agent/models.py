import uuid

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base, TimestampMixin, UUIDPKMixin


class AuditLog(UUIDPKMixin, TimestampMixin, Base):
    """Every sensitive-data access attempt by an agent tool — allowed or
    denied. See README: "Denied/successful sensitive retrievals are
    auditable."
    """

    __tablename__ = "audit_log"

    action: Mapped[str] = mapped_column(String, nullable=False)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    requested_sensitivity: Mapped[str] = mapped_column(String, nullable=False)
    resource_sensitivity: Mapped[str] = mapped_column(String, nullable=False)
    decision: Mapped[str] = mapped_column(String, nullable=False)  # "allowed" | "denied"
    detail: Mapped[str] = mapped_column(String, nullable=False, default="")
