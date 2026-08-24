"""Shared ingestion bookkeeping: content hashing, ingestion_run lifecycle,
and idempotent raw_record / source_event writes.

Every connector preserves raw data before any destructive transformation —
see README, "Ingests and preserves source data".
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ingestion.models import IngestionRun, RawRecord, SourceEvent, SourceRegistry


class UnregisteredSourceError(Exception):
    """Raised when a connector tries to ingest data under a source_id that has
    no source_registry entry. See README's quality gate: "Unregistered source
    tries to ingest data -> Reject ingestion".
    """


def content_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def start_ingestion_run(session: Session, source_id: str) -> IngestionRun:
    run = IngestionRun(source_id=source_id, status="running")
    session.add(run)
    session.flush()
    return run


def finish_ingestion_run(
    session: Session,
    run: IngestionRun,
    *,
    status: str = "succeeded",
    ingested: int = 0,
    quarantined: int = 0,
    rejected: int = 0,
    error: str | None = None,
) -> IngestionRun:
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.records_ingested = ingested
    run.records_quarantined = quarantined
    run.records_rejected = rejected
    run.error_message = error
    session.flush()
    return run


def upsert_raw_record(
    session: Session,
    *,
    source_id: str,
    ingestion_run_id: uuid.UUID,
    record_type: str,
    payload: dict,
    source_url: str | None = None,
) -> tuple[RawRecord, bool]:
    """Idempotent on (source_id, record_type, content_hash) so rerunning a
    fixed input creates no duplicate raw_record rows.

    Raises UnregisteredSourceError before writing anything if source_id has
    no source_registry entry.
    """
    if session.get(SourceRegistry, source_id) is None:
        raise UnregisteredSourceError(f"source_id={source_id!r} is not registered in source_registry")

    hash_ = content_hash(payload)
    existing = session.scalars(
        select(RawRecord).where(
            RawRecord.source_id == source_id,
            RawRecord.record_type == record_type,
            RawRecord.content_hash == hash_,
        )
    ).first()
    if existing is not None:
        return existing, False

    record = RawRecord(
        source_id=source_id,
        ingestion_run_id=ingestion_run_id,
        record_type=record_type,
        content_hash=hash_,
        raw_payload=payload,
        source_url=source_url,
    )
    session.add(record)
    session.flush()
    return record, True


def record_source_event(
    session: Session,
    *,
    source_id: str,
    event_type: str,
    status: str,
    payload: dict,
    raw_record_id: uuid.UUID | None = None,
) -> tuple[SourceEvent, bool]:
    """Idempotent on (source_id, event_type, content_hash of payload) so
    rerunning a fixed discovery feed creates no duplicate source_event rows.
    """
    hash_ = content_hash(payload)
    existing = session.scalars(
        select(SourceEvent).where(
            SourceEvent.source_id == source_id,
            SourceEvent.event_type == event_type,
            SourceEvent.content_hash == hash_,
        )
    ).first()
    if existing is not None:
        return existing, False

    event = SourceEvent(
        source_id=source_id,
        raw_record_id=raw_record_id,
        event_type=event_type,
        status=status,
        payload=payload,
        content_hash=hash_,
    )
    session.add(event)
    session.flush()
    return event, True
