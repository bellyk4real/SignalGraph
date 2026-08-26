# Data model

See the README's "Data model", "Funding rounds are first-class", and "Claim and provenance model" sections for the canonical description.

Implementation: `src/*/models.py` (SQLAlchemy) and `infra/migrations/` (Alembic), landing in Sprint 3 (`sprint-03-core-data-model`).

Core tables: `source_registry`, `ingestion_run`, `raw_record`, `source_event`, `entity`, `entity_identifier`, `entity_resolution_decision`, `funding_round`, `entity_relationship`, `claim`, `source_document`, `claim_evidence`, `document_chunk`, `communication`.
