select
    id as entity_id,
    entity_type,
    canonical_name,
    created_at
from {{ source('signalgraph_app', 'entity') }}
