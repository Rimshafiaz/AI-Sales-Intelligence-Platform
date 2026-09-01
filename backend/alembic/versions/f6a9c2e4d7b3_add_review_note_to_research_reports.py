"""add review_note to research reports

Revision ID: f6a9c2e4d7b3
Revises: e2f5a7c9d1b4
Create Date: 2026-09-01 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a9c2e4d7b3'
down_revision: Union[str, Sequence[str], None] = 'e2f5a7c9d1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'research_reports',
        sa.Column('review_note', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('research_reports', 'review_note')
