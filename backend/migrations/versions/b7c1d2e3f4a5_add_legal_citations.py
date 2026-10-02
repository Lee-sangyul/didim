"""add legal citations

Revision ID: b7c1d2e3f4a5
Revises: 8a20dac1bf7a
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c1d2e3f4a5"
down_revision: Union[str, Sequence[str], None] = "8a20dac1bf7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assessment",
        sa.Column("citations", sa.String(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("assessment", "citations")
