from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b2c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    website_audit_state = postgresql.ENUM(
        "not_run",
        "completed",
        "unavailable",
        name="website_audit_state",
        create_type=False,
    )
    website_audit_state.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "research_requests",
        sa.Column(
            "website_audit_state",
            website_audit_state,
            server_default="not_run",
            nullable=False,
        ),
    )
    op.add_column(
        "research_requests",
        sa.Column("website_audit_reason", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "research_requests",
        sa.Column("website_audited_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "research_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(length=100), nullable=False),
        sa.Column("evidence_type", sa.String(length=20), nullable=False),
        sa.Column("supporting_value", sa.String(length=1000), nullable=False),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("source_provider", sa.String(length=100), nullable=False),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
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
            "signal_type",
            "source_provider",
            name="uq_research_evidence_request_signal_provider",
        ),
    )
    op.create_index(
        "ix_research_evidence_research_request_id",
        "research_evidence",
        ["research_request_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_evidence_research_request_id", table_name="research_evidence")
    op.drop_table("research_evidence")
    op.drop_column("research_requests", "website_audited_at")
    op.drop_column("research_requests", "website_audit_reason")
    op.drop_column("research_requests", "website_audit_state")
    website_audit_state = postgresql.ENUM(
        "not_run",
        "completed",
        "unavailable",
        name="website_audit_state",
        create_type=False,
    )
    website_audit_state.drop(op.get_bind(), checkfirst=True)
