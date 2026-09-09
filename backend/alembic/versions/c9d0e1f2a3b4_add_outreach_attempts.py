from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    channel = postgresql.ENUM("email", "linkedin", name="outreach_channel", create_type=False)
    channel.create(op.get_bind(), checkfirst=True)
    send_method = postgresql.ENUM("gmail", "manual", name="outreach_send_method", create_type=False)
    send_method.create(op.get_bind(), checkfirst=True)
    outreach_status = postgresql.ENUM(
        "draft", "approved", "sending", "sent", "failed", "replied", "closed",
        name="outreach_status", create_type=False,
    )
    outreach_status.create(op.get_bind(), checkfirst=True)
    outcome = postgresql.ENUM(
        "interested", "not_interested", "bounced", "no_response",
        name="outreach_outcome", create_type=False,
    )
    outcome.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "outreach_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("campaign_prospect_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", channel, nullable=False),
        sa.Column("send_method", send_method, nullable=False),
        sa.Column("recipient", sa.String(length=2048), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("offering", sa.String(length=300), nullable=False),
        sa.Column("grounding_evidence_keys", postgresql.JSONB(), nullable=False),
        sa.Column("contact_source_keys", postgresql.JSONB(), nullable=False),
        sa.Column("edited_by_user", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("status", outreach_status, server_default="draft", nullable=False),
        sa.Column("outcome", outcome, nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("provider_thread_id", sa.String(length=255), nullable=True),
        sa.Column("failure_reason", sa.String(length=1000), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_prospect_id"], ["campaign_prospects.id"]),
        sa.ForeignKeyConstraint(["research_report_id"], ["research_reports.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outreach_attempts_campaign_prospect_id", "outreach_attempts", ["campaign_prospect_id"])
    op.create_index("ix_outreach_attempts_research_report_id", "outreach_attempts", ["research_report_id"])
    op.create_index("ix_outreach_attempts_user_id", "outreach_attempts", ["user_id"])
    op.create_index("ix_outreach_attempts_status", "outreach_attempts", ["status"])
    op.create_index(
        "uq_outreach_attempt_active_contact",
        "outreach_attempts",
        ["campaign_prospect_id", "research_report_id", "channel", "recipient"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'approved', 'sending')"),
    )


def downgrade() -> None:
    op.drop_index("uq_outreach_attempt_active_contact", table_name="outreach_attempts")
    op.drop_index("ix_outreach_attempts_status", table_name="outreach_attempts")
    op.drop_index("ix_outreach_attempts_user_id", table_name="outreach_attempts")
    op.drop_index("ix_outreach_attempts_research_report_id", table_name="outreach_attempts")
    op.drop_index("ix_outreach_attempts_campaign_prospect_id", table_name="outreach_attempts")
    op.drop_table("outreach_attempts")
    for enum_name in ("outreach_outcome", "outreach_status", "outreach_send_method", "outreach_channel"):
        postgresql.ENUM(name=enum_name, create_type=False).drop(op.get_bind(), checkfirst=True)
