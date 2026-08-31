"""create research reports table

Revision ID: c8f3a2b1d4e5
Revises: 1baf00613131
Create Date: 2026-08-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'c8f3a2b1d4e5'
down_revision: Union[str, Sequence[str], None] = '1baf00613131'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('research_reports',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('research_request_id', sa.UUID(), nullable=False),
    sa.Column('company_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('report_data', JSONB(), nullable=False),
    sa.Column('opportunity_score', sa.Integer(), nullable=True),
    sa.Column('contact_recommendation', sa.String(), nullable=True),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    sa.ForeignKeyConstraint(['research_request_id'], ['research_requests.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_research_reports_company_id'), 'research_reports', ['company_id'], unique=False)
    op.create_index(op.f('ix_research_reports_opportunity_score'), 'research_reports', ['opportunity_score'], unique=False)
    op.create_index(op.f('ix_research_reports_research_request_id'), 'research_reports', ['research_request_id'], unique=False)
    op.create_index(op.f('ix_research_reports_user_id'), 'research_reports', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_research_reports_user_id'), table_name='research_reports')
    op.drop_index(op.f('ix_research_reports_research_request_id'), table_name='research_reports')
    op.drop_index(op.f('ix_research_reports_opportunity_score'), table_name='research_reports')
    op.drop_index(op.f('ix_research_reports_company_id'), table_name='research_reports')
    op.drop_table('research_reports')
