# Threat model

## In scope
- False entity merges corrupting investment history or relationship context (mitigated by conservative, reversible entity resolution — see README "Entity resolution").
- Unvalidated or low-authority sources becoming agent-visible facts (mitigated by the source registry and claim lifecycle — see `adr-004-source-registry.md`, `adr-002-provenance-first-claims.md`).
- Restricted communications leaking through generic search or ranking (mitigated by permission filtering before retrieval — see README "Security and communications", implemented in Sprint 10).
- Screening-source (sanctions-style) hits being treated as automatic conclusions instead of review-only signals.

## Out of scope for the MVP
- Real customer/investor correspondence — the project uses synthetic communications only.
- Automated outreach or campaign execution.
- Multi-tenant/row-level access control (tracked in the README roadmap's "Later" section).
