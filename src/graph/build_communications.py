"""Materializes validated synthetic_communications raw_records into
Communication + CommunicationParticipant rows, resolving each named
participant to an entity.

Usage: uv run python -m src.graph.build_communications
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import get_session_factory
from src.graph.models import Communication, CommunicationParticipant, EntityType, Sensitivity
from src.ingestion.models import RawRecord
from src.resolution.matcher import get_or_create_entity

# Best-effort name -> entity_type mapping for the synthetic fixture set. A
# real pipeline would resolve participants the same conservative way
# vendor investors are resolved (src.resolution.matcher); this is a small,
# fixture-scoped lookup, not a general NER/resolution pipeline.
KNOWN_PARTICIPANT_TYPES: dict[str, EntityType] = {
    "GridFlow GmbH": EntityType.COMPANY,
    "Northstar Ventures": EntityType.INVESTOR_FIRM,
    "Example Capital": EntityType.INVESTOR_FIRM,
}


def _entity_type_for(name: str) -> EntityType:
    return KNOWN_PARTICIPANT_TYPES.get(name, EntityType.PERSON)


def build_communications(session: Session) -> int:
    already_built = set(
        session.scalars(select(Communication.raw_record_id).where(Communication.raw_record_id.is_not(None))).all()
    )
    records = session.scalars(
        select(RawRecord).where(RawRecord.record_type == "communication", RawRecord.validation_status == "valid")
    ).all()

    created = 0
    for record in records:
        if record.id in already_built:
            continue

        payload = record.raw_payload
        communication = Communication(
            source_id=record.source_id,
            raw_record_id=record.id,
            communication_type=payload["communication_type"],
            sensitivity=Sensitivity(payload["sensitivity"]),
            occurred_at=datetime.fromisoformat(payload["occurred_at"]),
            raw_text=payload["raw_text"],
            redacted_text=payload["redacted_text"],
        )
        session.add(communication)
        session.flush()

        for name in payload["participants"]:
            entity = get_or_create_entity(session, entity_type=_entity_type_for(name), canonical_name=name)
            session.add(CommunicationParticipant(communication_id=communication.id, entity_id=entity.id))

        created += 1

    session.flush()
    return created


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        created = build_communications(session)
        session.commit()
    print(f"materialized {created} new communication rows")


if __name__ == "__main__":
    main()
