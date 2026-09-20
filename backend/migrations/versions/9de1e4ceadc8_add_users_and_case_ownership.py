"""add users and case ownership

Revision ID: 9de1e4ceadc8
Revises: 0c5eff7e4c9a
Create Date: 2026-09-20 19:25:27.733326
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "9de1e4ceadc8"
down_revision: Union[str, Sequence[str], None] = "0c5eff7e4c9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """사용자 테이블과 상담 소유자 필드를 추가한다."""

    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "username",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "password_hash",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "name",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "role",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        ),
        sa.Column(
            "last_login_at",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_users_is_active"),
        "users",
        ["is_active"],
        unique=False,
    )

    op.create_index(
        op.f("ix_users_role"),
        "users",
        ["role"],
        unique=False,
    )

    op.create_index(
        op.f("ix_users_username"),
        "users",
        ["username"],
        unique=True,
    )

    op.add_column(
        "case",
        sa.Column(
            "owner_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_index(
        op.f("ix_case_owner_id"),
        "case",
        ["owner_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_case_owner_id_users",
        "case",
        "users",
        ["owner_id"],
        ["id"],
    )


def downgrade() -> None:
    """사용자 테이블과 상담 소유자 필드를 제거한다."""

    op.drop_constraint(
        "fk_case_owner_id_users",
        "case",
        type_="foreignkey",
    )

    op.drop_index(
        op.f("ix_case_owner_id"),
        table_name="case",
    )

    op.drop_column(
        "case",
        "owner_id",
    )

    op.drop_index(
        op.f("ix_users_username"),
        table_name="users",
    )

    op.drop_index(
        op.f("ix_users_role"),
        table_name="users",
    )

    op.drop_index(
        op.f("ix_users_is_active"),
        table_name="users",
    )

    op.drop_table("users")