"""앱을 import해야 하는 점검을 격리된 프로세스에서 실행한다.

사용: python -m scripts.checks.worker <task> [args]
환경변수(DATABASE_URL 등)는 오케스트레이터(scripts/check.py)가 설정한다.
마지막 줄에 `@@RESULT@@ [json]`을 출력한다.
"""
from __future__ import annotations

import json
import sys
import traceback

from .core import FAIL, PASS, RESULT_MARK, WARN, Result


def emit(results: list[Result]) -> None:
    print(RESULT_MARK + json.dumps([r.to_dict() for r in results], ensure_ascii=False))


def task_drift() -> list[Result]:
    """마이그레이션을 끝까지 적용한 DB와 SQLModel 모델이 일치하는지 (컬럼 누락 사고 방지)."""
    import os

    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine
    from sqlmodel import SQLModel

    from app import models  # noqa: F401

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        diff = compare_metadata(
            MigrationContext.configure(conn, opts={"compare_type": True}), SQLModel.metadata
        )
    if diff:
        return [Result("모델-마이그레이션 일치", FAIL, "차이: " + "; ".join(str(d)[:120] for d in diff[:8]))]
    return [Result("모델-마이그레이션 일치", PASS, "autogenerate 차이 없음")]


def task_e2e(label: str) -> list[Result]:
    from . import e2e

    return e2e.run_scenario(label)


def task_regress() -> list[Result]:
    from . import regressions

    return regressions.run_all()


TASKS = {"drift": task_drift, "e2e": task_e2e, "regress": task_regress}


def main() -> int:
    task, *args = sys.argv[1:]
    try:
        results = TASKS[task](*args)
    except Exception:
        results = [Result(f"worker:{task}", FAIL, traceback.format_exc()[-1500:])]
    emit(results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
