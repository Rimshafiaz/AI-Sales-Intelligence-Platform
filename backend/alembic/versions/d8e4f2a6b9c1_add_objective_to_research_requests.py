"""add objective to research requests

Revision ID: d8e4f2a6b9c1
Revises: f6a9c2e4d7b3
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'd8e4f2a6b9c1'
down_revision: Union[str, Sequence[str], None] = 'f6a9c2e4d7b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'research_requests',
        sa.Column('objective', JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('research_requests', 'objective')
