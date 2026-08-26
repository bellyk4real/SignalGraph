select
    source_id,
    source_name,
    authority_tier,
    can_create_accepted_claims,
    allowed_for_agent_retrieval,
    freshness_sla_hours
from {{ source('signalgraph_app', 'source_registry') }}
