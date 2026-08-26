"""Ingest the synthetic vendor funding-round and investor identity feeds.

Deliberately preserves invalid rows (bad date, negative amount, unrecognized
currency) as-is in raw_record — validation/quarantine happens downstream in
src/validation, never at ingestion time. See README's "Example faulty feed".

Usage: uv run python -m src.ingestion.synthetic_vendor
"""

import csv
from pathlib import Path

from src.db import get_session_factory
from src.ingestion.base import finish_ingestion_run, start_ingestion_run, upsert_raw_record

SOURCE_ID = "vendor_enrichment"
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"
FUNDING_ROUNDS_CSV = DATA_DIR / "vendor_funding_rounds.csv"
INVESTORS_CSV = DATA_DIR / "vendor_investors.csv"


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as session:
        run = start_ingestion_run(session, SOURCE_ID)
        ingested = 0

        for row in _read_csv(FUNDING_ROUNDS_CSV):
            _, created = upsert_raw_record(
                session,
                source_id=SOURCE_ID,
                ingestion_run_id=run.id,
                record_type="vendor_funding_round",
                payload=row,
            )
            ingested += int(created)

        for row in _read_csv(INVESTORS_CSV):
            _, created = upsert_raw_record(
                session,
                source_id=SOURCE_ID,
                ingestion_run_id=run.id,
                record_type="vendor_investor",
                payload=row,
            )
            ingested += int(created)

        finish_ingestion_run(session, run, ingested=ingested)
        session.commit()
        print(f"vendor_enrichment ingestion_run {run.id}: {ingested} new raw records")


if __name__ == "__main__":
    main()
