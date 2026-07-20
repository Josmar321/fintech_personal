"""add last_sync_date to email_sources (high-water mark)

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-20 00:15:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_sources",
        sa.Column(
            "last_sync_date",
            sa.DateTime(),
            nullable=True,
            comment="High-water mark for Yape Excel rows",
        ),
    )


def downgrade() -> None:
    op.drop_column("email_sources", "last_sync_date")
