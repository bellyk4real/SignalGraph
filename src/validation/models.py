import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base, TimestampMixin, UUIDPKMixin


class Quarantine(UUIDPKMixin, TimestampMixin, Base):
    """A raw_record (or ingestion attempt) blocked from entering the graph,
    with an explicit machine-readable reason code — see README's
    "Core quality gates" table.
    """

    __tablename__ = "quarantine"

    raw_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_record.id"), nullable=True
    )
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    reason_code: Mapped[str] = mapped_column(String, nullable=False)
    field_name: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[str] = mapped_column(String, nullable=False)
