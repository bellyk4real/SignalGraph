"""Applies the README's "Core quality gates" table to pending raw_record rows:
validates each against its Pydantic contract and either marks it valid or
quarantines it with a field-level, machine-readable reason code.

Usage: uv run python -m src.validation.quality_gates
"""

from dataclasses import dataclass

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import get_session_factory
from src.ingestion.models import RawRecord
from src.validation.models import Quarantine
from src.validation.schemas import (
    CommunicationRecord,
    OfficialDocumentRecord,
    VendorFundingRoundRecord,
    VendorInvestorRecord,
)

RECORD_TYPE_SCHEMAS: dict[str, type[BaseModel]] = {
    "vendor_funding_round": VendorFundingRoundRecord,
    "vendor_investor": VendorInvestorRecord,
    "communication": CommunicationRecord,
    "official_document": OfficialDocumentRecord,
}

# pydantic error type -> our reason code, per field, falls back to a generic
# "invalid_<field>" code when no specific mapping applies.
_FIELD_REASON_OVERRIDES = {
    "amount": "negative_amount",
    "currency": "invalid_currency",
    "announced_on": "invalid_date",
    "url": "invalid_url",
}


@dataclass
class ValidationSummary:
    valid: int = 0
    quarantined: int = 0
    unrecognized_type: int = 0


def _reason_code_for(field_name: str) -> str:
    return _FIELD_REASON_OVERRIDES.get(field_name, f"invalid_{field_name}")


def validate_raw_record(session: Session, record: RawRecord) -> bool:
    """Validates one raw_record, writes Quarantine rows on failure, and sets
    record.validation_status. Returns True if the record is valid.
    """
    schema = RECORD_TYPE_SCHEMAS.get(record.record_type)
    if schema is None:
        session.add(
            Quarantine(
                raw_record_id=record.id,
                source_id=record.source_id,
                reason_code="invalid_record_type",
                field_name="record_type",
                detail=f"No validation contract registered for record_type={record.record_type!r}",
            )
        )
        record.validation_status = "quarantined"
        return False

    try:
        schema.model_validate(record.raw_payload)
    except ValidationError as exc:
        for error in exc.errors():
            field_name = str(error["loc"][0]) if error["loc"] else "__root__"
            session.add(
                Quarantine(
                    raw_record_id=record.id,
                    source_id=record.source_id,
                    reason_code=_reason_code_for(field_name),
                    field_name=field_name,
                    detail=error["msg"],
                )
            )
        record.validation_status = "quarantined"
        return False

    record.validation_status = "valid"
    return True


def validate_pending_raw_records(session: Session) -> ValidationSummary:
    summary = ValidationSummary()
    pending = session.scalars(select(RawRecord).where(RawRecord.validation_status == "pending")).all()

    for record in pending:
        if validate_raw_record(session, record):
            summary.valid += 1
        elif record.record_type not in RECORD_TYPE_SCHEMAS:
            summary.unrecognized_type += 1
        else:
            summary.quarantined += 1

    session.commit()
    return summary


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        summary = validate_pending_raw_records(session)
    print(f"validated: {summary.valid} valid, {summary.quarantined} quarantined, {summary.unrecognized_type} unrecognized type")


if __name__ == "__main__":
    main()
