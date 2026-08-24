# ADR-004: Source registry as a first-class control plane

## Status
Accepted

## Decision
Every ingestion source is registered with an explicit authority tier, permitted claim types, freshness SLA, PII classification, and agent-retrieval eligibility, enforced before any record from that source can become an accepted, agent-visible claim.

## Rationale
Discovery is not evidence, and evidence is not truth without policy. A discovery feed like GDELT must never bypass source validation and become a canonical fact on its own. See README, "Source policy."
