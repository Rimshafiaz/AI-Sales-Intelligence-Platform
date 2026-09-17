"""add durable campaign candidate pool and research batch key

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaign_runs",
        sa.Column("candidate_pool_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "campaign_candidate_selections",
        sa.Column("research_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_campaign_candidate_selections_research_batch_id",
        "campaign_candidate_selections",
        ["research_batch_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_campaign_candidate_selections_research_batch_id",
        table_name="campaign_candidate_selections",
    )
    op.drop_column("campaign_candidate_selections", "research_batch_id")
    op.drop_column("campaign_runs", "candidate_pool_snapshot")
