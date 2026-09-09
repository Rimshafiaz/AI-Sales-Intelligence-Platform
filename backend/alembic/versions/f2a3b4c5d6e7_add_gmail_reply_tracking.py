from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, Sequence[str], None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "outreach_attempts",
        sa.Column("provider_reply_message_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outreach_attempts", "provider_reply_message_id")
