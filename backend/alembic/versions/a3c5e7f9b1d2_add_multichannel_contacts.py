from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3c5e7f9b1d2"
down_revision: Union[str, Sequence[str], None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in ("instagram", "facebook", "whatsapp", "phone", "contact_form"):
        op.execute(f"ALTER TYPE outreach_channel ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column(
        "research_social_observations",
        sa.Column(
            "public_emails",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "research_social_observations",
        sa.Column(
            "public_phones",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("research_social_observations", "public_phones")
    op.drop_column("research_social_observations", "public_emails")
