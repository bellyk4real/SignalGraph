# ADR-001: Postgres relational tables instead of a dedicated graph database

## Status
Accepted

## Decision
Model the graph as relational node/edge tables in PostgreSQL rather than adopting a separate graph database.

## Rationale
Graph traversal, transactional integrity, document search, quality gates, and operational state need to live in one platform. Postgres is sufficient at the intended MVP graph scale and avoids running/operating a second stateful system. See README, "PostgreSQL rather than a dedicated graph database."
