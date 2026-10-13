"""recompute document_delete_after with the 5-year retention policy

기존 신청서는 '신청 후 30일'로 기록돼 있다. 5년 보관 정책에 맞춰
(심사일 또는 신청일) + 5년으로 다시 계산한다. 이 값을 쓰는 삭제 작업(purge)이
정책보다 일찍 문서를 지우지 않게 하기 위한 데이터 마이그레이션이다.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
"""
from datetime import datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RETENTION_YEARS = 5  # app/services/retention.py 와 같은 값 (마이그레이션은 앱 코드를 import하지 않는다)


def _plus_years(value: str) -> str:
    start = datetime.fromisoformat(value)
    try:
        return start.replace(year=start.year + RETENTION_YEARS).isoformat()
    except ValueError:  # 2월 29일
        return start.replace(year=start.year + RETENTION_YEARS, day=28).isoformat()


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, created_at, reviewed_at FROM registration_applications")
    ).fetchall()

    for row_id, created_at, reviewed_at in rows:
        base = reviewed_at or created_at

        try:
            deadline = _plus_years(base)
        except (TypeError, ValueError):
            continue  # 날짜를 읽을 수 없는 행은 건드리지 않는다

        bind.execute(
            sa.text("UPDATE registration_applications SET document_delete_after = :d WHERE id = :i"),
            {"d": deadline, "i": row_id},
        )


def downgrade() -> None:
    # 이전 값(신청 후 30일)을 복원할 수 없다. 데이터 정책 변경이므로 되돌리지 않는다.
    pass
