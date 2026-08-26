"""Ingest the synthetic communications corpus as raw_record rows.

Raw text is preserved as-is here; separating it into restricted `communication`
rows with permission-aware access happens once entities are resolved
(src/graph, Sprint 6+) and permissions are enforced (Sprint 10).

Usage: uv run python -m src.ingestion.synthetic_communications
"""

import json
from pathlib import Path

from src.db import get_session_factory
from src.ingestion.base import finish_ingestion_run, start_ingestion_run, upsert_raw_record

SOURCE_ID = "synthetic_communications"
COMMUNICATIONS_JSON = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "communications.json"


def main() -> None:
    records = json.loads(COMMUNICATIONS_JSON.read_text())

    session_factory = get_session_factory()
    with session_factory() as session:
        run = start_ingestion_run(session, SOURCE_ID)
        ingested = 0

        for record in records:
            _, created = upsert_raw_record(
                session,
                source_id=SOURCE_ID,
                ingestion_run_id=run.id,
                record_type="communication",
                payload=record,
            )
            ingested += int(created)

        finish_ingestion_run(session, run, ingested=ingested)
        session.commit()
        print(f"synthetic_communications ingestion_run {run.id}: {ingested} new raw records")


if __name__ == "__main__":
    main()
