from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    social_audit_state = postgresql.ENUM(
        "not_run",
        "completed",
        "unavailable",
        name="social_audit_state",
        create_type=False,
    )
    social_audit_state.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "research_requests",
        sa.Column(
            "social_audit_state",
            social_audit_state,
            server_default="not_run",
            nullable=False,
        ),
    )
    op.add_column(
        "research_requests",
        sa.Column("social_audit_reason", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "research_requests",
        sa.Column("social_audited_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "research_evidence",
        sa.Column("source_identity_key", sa.String(length=400), nullable=True),
    )
    op.execute(
        "UPDATE research_evidence SET source_identity_key = "
        "left(source_provider || ':' || source_url, 400)"
    )
    op.alter_column("research_evidence", "source_identity_key", nullable=False)
    op.drop_constraint(
        "uq_research_evidence_request_signal_provider",
        "research_evidence",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_research_evidence_request_signal_source",
        "research_evidence",
        ["research_request_id", "signal_type", "source_identity_key"],
    )

    op.create_table(
        "research_social_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("profile_identity_key", sa.String(length=400), nullable=False),
        sa.Column("platform", sa.String(length=30), nullable=False),
        sa.Column("profile_url", sa.String(length=2048), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("handle", sa.String(length=255), nullable=True),
        sa.Column("external_url", sa.String(length=2048), nullable=True),
        sa.Column("provider_profile_id", sa.String(length=255), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=True),
        sa.Column("latest_public_post_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recent_public_post_dates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_provider", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["research_request_id"], ["research_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "research_request_id",
            "profile_identity_key",
            name="uq_research_social_observation_request_profile",
        ),
    )
    op.create_index(
        "ix_research_social_observations_research_request_id",
        "research_social_observations",
        ["research_request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_social_observations_research_request_id",
        table_name="research_social_observations",
    )
    op.drop_table("research_social_observations")
    op.drop_constraint(
        "uq_research_evidence_request_signal_source",
        "research_evidence",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_research_evidence_request_signal_provider",
        "research_evidence",
        ["research_request_id", "signal_type", "source_provider"],
    )
    op.drop_column("research_evidence", "source_identity_key")
    op.drop_column("research_requests", "social_audited_at")
    op.drop_column("research_requests", "social_audit_reason")
    op.drop_column("research_requests", "social_audit_state")
    social_audit_state = postgresql.ENUM(
        "not_run",
        "completed",
        "unavailable",
        name="social_audit_state",
        create_type=False,
    )
    social_audit_state.drop(op.get_bind(), checkfirst=True)
