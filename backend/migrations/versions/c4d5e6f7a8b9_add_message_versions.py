"""add message versions (answer regeneration)

Revision ID: c4d5e6f7a8b9
Revises: b7c1d2e3f4a5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b7c1d2e3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "message",
        sa.Column("versions", sa.String(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("message", "versions")
