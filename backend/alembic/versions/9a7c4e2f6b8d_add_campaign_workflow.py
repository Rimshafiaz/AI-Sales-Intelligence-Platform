from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "9a7c4e2f6b8d"
down_revision: Union[str, Sequence[str], None] = "d8e4f2a6b9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    campaign_run_status = postgresql.ENUM(
        "completed",
        name="campaign_run_status",
        create_type=False,
    )
    campaign_run_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("goal", sa.String(length=2000), nullable=True),
        sa.Column("discovery_criteria", postgresql.JSONB(), nullable=False),
        sa.Column("model_selection", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_user_id", "campaigns", ["user_id"])

    op.create_table(
        "campaign_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            campaign_run_status,
            server_default="completed",
            nullable=False,
        ),
        sa.Column("criteria_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("model_selection_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("provider_summary", postgresql.JSONB(), nullable=False),
        sa.Column("discovered_candidate_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_runs_campaign_id", "campaign_runs", ["campaign_id"])

    op.add_column(
        "companies",
        sa.Column("identity_key", sa.String(length=400), nullable=True),
    )
    op.create_unique_constraint(
        "uq_companies_user_identity_key",
        "companies",
        ["user_id", "identity_key"],
    )

    op.create_table(
        "campaign_candidate_selections",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_identity_key", sa.String(length=400), nullable=False),
        sa.Column("candidate_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("shortlist_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campaign_run_id"], ["campaign_runs.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "campaign_run_id",
            "source_identity_key",
            name="uq_campaign_run_source_identity",
        ),
    )
    op.create_index(
        "ix_campaign_candidate_selections_campaign_run_id",
        "campaign_candidate_selections",
        ["campaign_run_id"],
    )
    op.create_index(
        "ix_campaign_candidate_selections_company_id",
        "campaign_candidate_selections",
        ["company_id"],
    )

    op.add_column(
        "research_requests",
        sa.Column(
            "campaign_candidate_selection_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_research_requests_campaign_candidate_selection",
        "research_requests",
        "campaign_candidate_selections",
        ["campaign_candidate_selection_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_research_requests_campaign_candidate_selection",
        "research_requests",
        ["campaign_candidate_selection_id"],
    )
    op.create_index(
        "ix_research_requests_campaign_candidate_selection_id",
        "research_requests",
        ["campaign_candidate_selection_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_requests_campaign_candidate_selection_id",
        table_name="research_requests",
    )
    op.drop_constraint(
        "uq_research_requests_campaign_candidate_selection",
        "research_requests",
        type_="unique",
    )
    op.drop_constraint(
        "fk_research_requests_campaign_candidate_selection",
        "research_requests",
        type_="foreignkey",
    )
    op.drop_column("research_requests", "campaign_candidate_selection_id")
    op.drop_index(
        "ix_campaign_candidate_selections_company_id",
        table_name="campaign_candidate_selections",
    )
    op.drop_index(
        "ix_campaign_candidate_selections_campaign_run_id",
        table_name="campaign_candidate_selections",
    )
    op.drop_table("campaign_candidate_selections")
    op.drop_constraint(
        "uq_companies_user_identity_key",
        "companies",
        type_="unique",
    )
    op.drop_column("companies", "identity_key")
    op.drop_index("ix_campaign_runs_campaign_id", table_name="campaign_runs")
    op.drop_table("campaign_runs")
    op.drop_index("ix_campaigns_user_id", table_name="campaigns")
    op.drop_table("campaigns")
    campaign_run_status = postgresql.ENUM(
        "completed",
        name="campaign_run_status",
        create_type=False,
    )
    campaign_run_status.drop(op.get_bind(), checkfirst=True)
