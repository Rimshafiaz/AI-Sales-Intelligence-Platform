from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    report_kind = sa.Enum(
        "sales_intelligence",
        "prospect_evidence_brief",
        name="report_kind",
    )
    report_kind.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "research_reports",
        sa.Column(
            "report_kind",
            report_kind,
            server_default="sales_intelligence",
            nullable=False,
        ),
    )
    op.create_index(
        "ix_research_reports_report_kind",
        "research_reports",
        ["report_kind"],
        unique=False,
    )
    op.alter_column("research_reports", "opportunity_score", nullable=True)
    op.alter_column("research_reports", "contact_recommendation", nullable=True)


def downgrade() -> None:
    op.alter_column("research_reports", "contact_recommendation", nullable=False)
    op.alter_column("research_reports", "opportunity_score", nullable=False)
    op.drop_index("ix_research_reports_report_kind", table_name="research_reports")
    op.drop_column("research_reports", "report_kind")
    sa.Enum(name="report_kind").drop(op.get_bind(), checkfirst=True)
