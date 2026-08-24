-- dbt-level regression guard mirroring README's quality gate: "Accepted
-- claim has no evidence -> Prevent agent visibility". Passes when this
-- query returns zero rows.
select c.claim_id
from {{ ref('stg_claims') }} c
left join {{ source('signalgraph_app', 'claim_evidence') }} ce on ce.claim_id = c.claim_id
where c.status = 'accepted'
group by c.claim_id
having count(ce.id) = 0
