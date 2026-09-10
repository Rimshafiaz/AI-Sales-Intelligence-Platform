"""add not_a_fit campaign prospect state

Revision ID: b2c4d6e8f0a2
Revises: a3c5e7f9b1d2
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b2c4d6e8f0a2'
down_revision: Union[str, Sequence[str], None] = 'a3c5e7f9b1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE campaign_prospect_state ADD VALUE IF NOT EXISTS 'not_a_fit'"
    )


def downgrade() -> None:
    # Removing an enum value is not supported by PostgreSQL; the value stays
    # unused if this migration is reverted.
    pass
