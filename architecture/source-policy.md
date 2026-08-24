# Source policy

See the README's "Source policy" section for the authority-tier table and the example `source_registry` record.

Implementation: `data/source_registry.yml` (the registry data) and `src/ingestion/load_source_registry.py` (the idempotent loader), landing in Sprint 2 (`sprint-02-source-registry`). Enforcement of the policy (which sources may create accepted claims, freshness SLAs, quarantine reasons) lands in Sprint 5 (`sprint-05-validation-quarantine`).
