"""add social research state

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_requests",
        sa.Column("social_check_states", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "research_social_observations",
        sa.Column("biography", sa.String(length=2000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_social_observations", "biography")
    op.drop_column("research_requests", "social_check_states")
