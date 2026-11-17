"""add keyword_mappings table for learned keyword categorization

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-23 13:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "keyword_mappings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("keyword", sa.String(100), nullable=False),
        sa.Column("category_name", sa.String(100), nullable=False),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("keyword_mappings")
