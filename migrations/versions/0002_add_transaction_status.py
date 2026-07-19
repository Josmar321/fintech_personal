"""add status to transactions + make account_id nullable

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-19 23:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending_category'"),
        ),
    )
    op.alter_column("transactions", "account_id", nullable=True)


def downgrade() -> None:
    op.drop_column("transactions", "status")
    op.alter_column("transactions", "account_id", nullable=False)
