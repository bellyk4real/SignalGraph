-- The agent-safe view: accepted, evidence-backed, source-authorized claims.
-- Mirrors README: "Only claims that are accepted, evidence-backed, permitted
-- by source policy, non-expired, and authorised for the calling context are
-- visible to agents by default." Staleness is surfaced as `is_fresh` rather
-- than filtered out, so retrieval can disclose it as a caveat instead of
-- silently hiding the claim.

with claims as (
    select * from {{ ref('stg_claims') }}
),

registry as (
    select * from {{ ref('stg_source_registry') }}
),

entities as (
    select * from {{ ref('stg_entities') }}
),

evidence_counts as (
    select claim_id, count(*) as evidence_count
    from {{ source('signalgraph_app', 'claim_evidence') }}
    group by claim_id
)

select
    c.claim_id,
    c.subject_entity_id,
    e.canonical_name as subject_name,
    e.entity_type as subject_type,
    c.claim_type,
    c.claim_value,
    c.source_id,
    r.source_name,
    r.authority_tier,
    c.confidence,
    c.valid_from,
    c.valid_until,
    coalesce(ev.evidence_count, 0) as evidence_count,
    (c.valid_until is null or c.valid_until > now()) as is_fresh
from claims c
inner join entities e on e.entity_id = c.subject_entity_id
inner join registry r on r.source_id = c.source_id
left join evidence_counts ev on ev.claim_id = c.claim_id
where c.status = 'accepted'
  and r.allowed_for_agent_retrieval = true
  and coalesce(ev.evidence_count, 0) > 0
