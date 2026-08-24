select
    id as claim_id,
    subject_entity_id,
    entity_relationship_id,
    claim_type,
    claim_value,
    status,
    source_id,
    confidence,
    valid_from,
    valid_until,
    created_at
from {{ source('signalgraph_app', 'claim') }}
