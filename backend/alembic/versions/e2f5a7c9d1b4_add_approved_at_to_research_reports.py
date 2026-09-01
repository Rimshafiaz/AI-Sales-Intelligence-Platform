"""add approved_at to research reports

Revision ID: e2f5a7c9d1b4
Revises: c8f3a2b1d4e5
Create Date: 2026-09-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f5a7c9d1b4'
down_revision: Union[str, Sequence[str], None] = 'c8f3a2b1d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'research_reports',
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('research_reports', 'approved_at')
