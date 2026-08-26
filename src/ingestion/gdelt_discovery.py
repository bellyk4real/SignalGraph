"""Ingest GDELT-style discovery events.

A discovery event is recorded as a source_event ONLY — it never creates a
raw_record or claim by itself. See README's "Core product principle":
"Discovery is not evidence." Turning a discovery into evidence requires a
separate connector (e.g. official_documents.py) to fetch and validate the
original publisher/press release.

Usage: uv run python -m src.ingestion.gdelt_discovery
"""

import json
from pathlib import Path

from src.db import get_session_factory
from src.ingestion.base import record_source_event

SOURCE_ID = "gdelt"
EVENTS_JSON = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "gdelt_events.json"


def main() -> None:
    events = json.loads(EVENTS_JSON.read_text())

    session_factory = get_session_factory()
    with session_factory() as session:
        for event in events:
            record_source_event(
                session,
                source_id=SOURCE_ID,
                event_type="discovered",
                status="discovered_only",
                payload=event,
            )
        session.commit()
        print(f"gdelt: recorded {len(events)} discovery-only source_event rows (no raw_record/claim created)")


if __name__ == "__main__":
    main()
