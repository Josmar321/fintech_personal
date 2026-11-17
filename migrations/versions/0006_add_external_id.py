"""add external_id to transactions for yape dedup

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-23 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("external_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_transactions_external_id", "transactions", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_external_id")
    op.drop_column("transactions", "external_id")
