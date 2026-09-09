from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    prospect_state = postgresql.ENUM(
        "saved",
        "needs_research",
        "ready_for_outreach",
        "closed",
        name="campaign_prospect_state",
        create_type=False,
    )
    prospect_state.create(op.get_bind(), checkfirst=True)
    next_action = postgresql.ENUM(
        "research_prospect",
        "collect_evidence",
        "prepare_outreach",
        "no_action",
        name="campaign_prospect_next_action",
        create_type=False,
    )
    next_action.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "campaign_prospects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_identity_key", sa.String(length=400), nullable=False),
        sa.Column("candidate_index", sa.Integer(), nullable=False),
        sa.Column("candidate_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("shortlist_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("workflow_state", prospect_state, server_default="saved", nullable=False),
        sa.Column("next_action", next_action, server_default="research_prospect", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.ForeignKeyConstraint(["campaign_run_id"], ["campaign_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "source_identity_key", name="uq_campaign_prospect_campaign_source"),
    )
    op.create_index("ix_campaign_prospects_campaign_id", "campaign_prospects", ["campaign_id"])
    op.create_index("ix_campaign_prospects_campaign_run_id", "campaign_prospects", ["campaign_run_id"])
    op.create_index("ix_campaign_prospects_workflow_state", "campaign_prospects", ["workflow_state"])


def downgrade() -> None:
    op.drop_index("ix_campaign_prospects_workflow_state", table_name="campaign_prospects")
    op.drop_index("ix_campaign_prospects_campaign_run_id", table_name="campaign_prospects")
    op.drop_index("ix_campaign_prospects_campaign_id", table_name="campaign_prospects")
    op.drop_table("campaign_prospects")
    next_action = postgresql.ENUM(name="campaign_prospect_next_action", create_type=False)
    next_action.drop(op.get_bind(), checkfirst=True)
    prospect_state = postgresql.ENUM(name="campaign_prospect_state", create_type=False)
    prospect_state.drop(op.get_bind(), checkfirst=True)
