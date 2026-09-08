from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "opportunity_qualifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("research_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("opportunity_model_id", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column(
            "supporting_evidence_keys",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
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
            "opportunity_model_id",
            name="uq_opportunity_qualification_request_model",
        ),
    )
    op.create_index(
        "ix_opportunity_qualifications_research_request_id",
        "opportunity_qualifications",
        ["research_request_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_qualifications_research_request_id",
        table_name="opportunity_qualifications",
    )
    op.drop_table("opportunity_qualifications")
