# Architecture

See the "Architecture" and "Hybrid retrieval for agents" sections of the root [README](../README.md) for the full source-registry → ingestion → validation → canonical graph → claims/documents → agent-retrieval pipeline diagram.

This document tracks implementation-level detail as sprints land:

- `infra/docker-compose.yml` + `infra/migrations/` — local Postgres/pgvector environment (Sprint 1).
- `src/db.py` — SQLAlchemy engine/session used by every layer.
- `src/ingestion/`, `src/validation/`, `src/resolution/`, `src/enrichment/`, `src/retrieval/`, `src/agent/` — one package per pipeline stage, matching the README repository structure.
