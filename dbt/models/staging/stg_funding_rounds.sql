select
    id as funding_round_id,
    company_entity_id,
    round_type,
    amount,
    currency,
    announced_on
from {{ source('signalgraph_app', 'funding_round') }}
