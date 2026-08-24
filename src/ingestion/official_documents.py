"""Ingest curated first-party documents (investor thesis pages, press
releases). Each document's `source_id` field in the fixture selects the
source_registry entry that governs it (first_party_website or
first_party_announcement).

Usage: uv run python -m src.ingestion.official_documents
"""

import json
from pathlib import Path

from src.db import get_session_factory
from src.ingestion.base import finish_ingestion_run, start_ingestion_run, upsert_raw_record

DOCUMENTS_JSON = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "official_documents.json"


def main() -> None:
    documents = json.loads(DOCUMENTS_JSON.read_text())

    session_factory = get_session_factory()
    with session_factory() as session:
        runs_by_source = {}
        ingested_by_source: dict[str, int] = {}

        for document in documents:
            source_id = document["source_id"]
            if source_id not in runs_by_source:
                runs_by_source[source_id] = start_ingestion_run(session, source_id)
                ingested_by_source[source_id] = 0

            _, created = upsert_raw_record(
                session,
                source_id=source_id,
                ingestion_run_id=runs_by_source[source_id].id,
                record_type="official_document",
                payload=document,
                source_url=document.get("url"),
            )
            ingested_by_source[source_id] += int(created)

        for source_id, run in runs_by_source.items():
            finish_ingestion_run(session, run, ingested=ingested_by_source[source_id])

        session.commit()
        for source_id, count in ingested_by_source.items():
            print(f"{source_id} ingestion_run {runs_by_source[source_id].id}: {count} new raw records")


if __name__ == "__main__":
    main()
