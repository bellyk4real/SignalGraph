# ADR-002: Claims with evidence instead of overwritten entity attributes

## Status
Accepted

## Decision
Business facts are never written directly onto an entity record. Every assertion is stored as a `claim`, linked to `claim_evidence`, source policy, status, confidence, and validity, with an explicit lifecycle: `candidate → accepted → disputed → superseded → rejected`.

## Rationale
A company/investor fact can be stale, disputed, source-specific, or superseded. Claims make disagreement and correction explicit while still letting agents read a current, agent-safe view. See README, "Claim and provenance model."
