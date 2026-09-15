"""add research specialist state

Revision ID: c3d4e5f6a7b8
Revises: b2c4d6e8f0a2
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c4d6e8f0a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "research_requests",
        sa.Column("opportunity_model_selection", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "research_requests",
        sa.Column("specialist_outputs", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "research_requests",
        sa.Column("website_check_states", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_requests", "website_check_states")
    op.drop_column("research_requests", "specialist_outputs")
    op.drop_column("research_requests", "opportunity_model_selection")
