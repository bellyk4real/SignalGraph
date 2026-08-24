"""fix enum types to use lowercase values matching README vocabulary

Revision ID: b5e7f2574b61
Revises: 84f097d63445
Create Date: 2026-08-24 15:47:47.523554

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e7f2574b61'
down_revision: Union[str, Sequence[str], None] = '84f097d63445'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """SQLAlchemy's Enum(py_enum) persists the Python member *name*
    ("CANDIDATE") by default, not its lowercase `.value` ("candidate"). The
    four native Postgres enums created in earlier migrations therefore hold
    uppercase labels, diverging from the lowercase vocabulary documented in
    the README and now relied on by dbt (see src/graph/models.pg_enum).
    Recreates each enum type with the correct values and backfills existing
    rows; `lower(column::text)` reconstructs the intended value for every
    current member of every one of these enums.
    """
    # dbt-managed views (dbt/models/) depend on these columns and block
    # ALTER COLUMN TYPE; drop them here, `dbt build` recreates them afterward.
    op.execute("DROP VIEW IF EXISTS mart_current_accepted_claims CASCADE")
    op.execute("DROP VIEW IF EXISTS stg_entities CASCADE")
    op.execute("DROP VIEW IF EXISTS stg_claims CASCADE")
    op.execute("DROP VIEW IF EXISTS stg_funding_rounds CASCADE")
    op.execute("DROP VIEW IF EXISTS stg_source_registry CASCADE")

    op.execute("ALTER TYPE entity_type RENAME TO entity_type_old")
    op.execute("CREATE TYPE entity_type AS ENUM ('company', 'investor_firm', 'person', 'fund')")
    op.execute(
        "ALTER TABLE entity ALTER COLUMN entity_type TYPE entity_type "
        "USING lower(entity_type::text)::entity_type"
    )
    op.execute("DROP TYPE entity_type_old")

    op.execute("ALTER TYPE resolution_decision_type RENAME TO resolution_decision_type_old")
    op.execute("CREATE TYPE resolution_decision_type AS ENUM ('match', 'no_match', 'needs_review')")
    op.execute(
        "ALTER TABLE entity_resolution_decision ALTER COLUMN decision TYPE resolution_decision_type "
        "USING lower(decision::text)::resolution_decision_type"
    )
    op.execute("DROP TYPE resolution_decision_type_old")

    op.execute("ALTER TYPE claim_status RENAME TO claim_status_old")
    op.execute("CREATE TYPE claim_status AS ENUM ('candidate', 'accepted', 'disputed', 'superseded', 'rejected')")
    op.execute(
        "ALTER TABLE claim ALTER COLUMN status TYPE claim_status USING lower(status::text)::claim_status"
    )
    op.execute("DROP TYPE claim_status_old")

    op.execute("ALTER TYPE sensitivity RENAME TO sensitivity_old")
    op.execute("CREATE TYPE sensitivity AS ENUM ('public', 'internal', 'restricted')")
    op.execute(
        "ALTER TABLE source_document ALTER COLUMN sensitivity TYPE sensitivity "
        "USING lower(sensitivity::text)::sensitivity"
    )
    op.execute(
        "ALTER TABLE communication ALTER COLUMN sensitivity TYPE sensitivity "
        "USING lower(sensitivity::text)::sensitivity"
    )
    op.execute("DROP TYPE sensitivity_old")


def downgrade() -> None:
    raise NotImplementedError(
        "This migration corrects a data/schema bug from Sprint 3 (uppercase enum "
        "labels). Downgrading would reintroduce it; reset the dev database instead."
    )
