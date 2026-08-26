# Demo walkthrough

Runs the full SignalGraph pipeline against the synthetic fixtures and prints
each step as it happens.

```bash
docker compose -f infra/docker-compose.yml up -d postgres
uv run alembic upgrade head
uv run python -m demo.run_investor_matching
```

The script performs the README's 14-step demo walkthrough in order:

1. Start PostgreSQL/pgvector and load the source registry.
2. Ingest registry fixtures, synthetic vendor records, and curated official documents.
3. Inspect raw payload preservation, content hashes, ingestion metrics, and source metadata.
4. Show malformed funding data routed to quarantine with an explicit reason.
5. Resolve Northstar Ventures and North Star Ventures through legal/domain evidence.
6. Keep similarly named investors separate because identity evidence is insufficient.
7. Ingest a GDELT-style discovery event and show it creates only a discovery event.
8. Validate a first-party announcement and accept an evidence-backed funding-round claim.
9. Traverse the graph: investor → led/participated_in → funding round ← received_capital_in ← company.
10. Run investor matching and inspect structured recommendations, evidence excerpts, and caveats.
11. Submit an unsupported question and confirm the agent returns `insufficient_evidence`.
12. Retrieve a permitted communication and show the "not a warm introduction" constraint.
13. Repeat under insufficient permission and show deny/audit behaviour.
14. Update a source document and show targeted downstream refresh — **not yet implemented**; incremental
    document refresh is a near-term roadmap item (see README "Roadmap").

Sample output from steps 10 and 11 is captured in `example_outputs/matching_run.json` and
`example_outputs/insufficient_evidence_run.json`.

## Re-running from a clean slate

The pipeline is idempotent, but for a fully clean run (matching a first-time `docker compose up`):

```bash
docker compose -f infra/docker-compose.yml down -v
docker compose -f infra/docker-compose.yml up -d postgres
uv run alembic upgrade head
uv run python -m demo.run_investor_matching
```
