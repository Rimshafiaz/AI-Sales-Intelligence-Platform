from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b2c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "9a7c4e2f6b8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    evidence_gate_state = postgresql.ENUM(
        "not_run",
        "ready_for_deeper_research",
        "needs_review",
        name="evidence_gate_state",
        create_type=False,
    )
    evidence_gate_state.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "research_requests",
        sa.Column(
            "evidence_gate_state",
            evidence_gate_state,
            server_default="not_run",
            nullable=False,
        ),
    )
    op.add_column(
        "research_requests",
        sa.Column("evidence_gate_reason", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "research_requests",
        sa.Column("evidence_gated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_research_requests_evidence_gate_state",
        "research_requests",
        ["evidence_gate_state"],
    )

    op.add_column(
        "research_sources",
        sa.Column(
            "admission_state",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
    )
    op.add_column(
        "research_sources",
        sa.Column("admission_reason", sa.String(length=1000), nullable=True),
    )
    op.create_index(
        "ix_research_sources_admission_state",
        "research_sources",
        ["admission_state"],
    )


def downgrade() -> None:
    op.drop_index("ix_research_sources_admission_state", table_name="research_sources")
    op.drop_column("research_sources", "admission_reason")
    op.drop_column("research_sources", "admission_state")
    op.drop_index(
        "ix_research_requests_evidence_gate_state",
        table_name="research_requests",
    )
    op.drop_column("research_requests", "evidence_gated_at")
    op.drop_column("research_requests", "evidence_gate_reason")
    op.drop_column("research_requests", "evidence_gate_state")
    evidence_gate_state = postgresql.ENUM(
        "not_run",
        "ready_for_deeper_research",
        "needs_review",
        name="evidence_gate_state",
        create_type=False,
    )
    evidence_gate_state.drop(op.get_bind(), checkfirst=True)
