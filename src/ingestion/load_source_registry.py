"""Idempotently load data/source_registry.yml into the source_registry table.

Usage: uv run python -m src.ingestion.load_source_registry
"""

from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import get_session_factory
from src.ingestion.models import SourceRegistry
from src.ingestion.schemas import SourceRegistryEntry

DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "data" / "source_registry.yml"


def load_registry_entries(path: Path = DEFAULT_REGISTRY_PATH) -> list[SourceRegistryEntry]:
    raw = yaml.safe_load(path.read_text())
    return [SourceRegistryEntry.model_validate(entry) for entry in raw.get("sources", [])]


def upsert_source_registry(session: Session, entries: list[SourceRegistryEntry]) -> int:
    """Upsert each entry by source_id. Returns the number of entries applied.
    Safe to call repeatedly against the same fixture without creating duplicates.
    """
    existing = {row.source_id: row for row in session.scalars(select(SourceRegistry))}

    for entry in entries:
        data = entry.model_dump()
        row = existing.get(entry.source_id)
        if row is None:
            session.add(SourceRegistry(**data))
        else:
            for field, value in data.items():
                setattr(row, field, value)

    session.commit()
    return len(entries)


def main() -> None:
    entries = load_registry_entries()
    session_factory = get_session_factory()
    with session_factory() as session:
        count = upsert_source_registry(session, entries)
    print(f"Loaded {count} source_registry entries from {DEFAULT_REGISTRY_PATH}")


if __name__ == "__main__":
    main()
