"""서버가 시작할 때 DB 스키마(alembic 마이그레이션) 상태를 확인하고, 빈 DB면 처음 한 번 만들어 준다.

정책 (운영 데이터 보호가 최우선)
- 비어 있는 DB(앱 테이블도 alembic_version도 없음): 자동으로 `upgrade head` — 지울 데이터가 없다.
  새 PC에서 .env만 맞추고 start만 해도 동작하게 하기 위한 것이다.
- 이미 데이터가 있는 DB가 코드보다 뒤처져 있으면: **자동으로 바꾸지 않는다.** 크게 경고하고
  `python -m scripts.migrate --upgrade`(또는 alembic upgrade head)를 사람이 실행하게 한다. (R016)
- SQLite는 앱이 직접 테이블을 만든다(init_sqlite_schema). 이 모듈은 Postgres용이다.
실패해도 서버 시작을 막지 않는다 — 상태는 /api/health/db 로 확인한다.
"""
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
ADVISORY_LOCK_ID = 727274  # 여러 서버 프로세스가 동시에 빈 DB를 만들지 않도록
APP_TABLES = {"users", "case", "message", "assessment", "attachment"}


def alembic_config(engine: Engine | None = None) -> Config:
    """현재 작업 폴더와 무관하게 동작하는 alembic 설정 (backend/alembic.ini).

    engine을 주면 그 DB에 적용한다(주지 않으면 .env의 DATABASE_URL). 비밀번호가 든 주소는 메모리에만 둔다.
    """
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    # 서버 안에서 실행될 때 alembic이 앱의 로깅 설정을 덮어쓰지 않게 한다 (env.py 참고)
    cfg.attributes["configure_logger"] = False

    if engine is not None:
        url = engine.url.render_as_string(hide_password=False).replace("%", "%%")
        cfg.set_main_option("sqlalchemy.url", url)
        cfg.attributes["keep_url"] = True

    return cfg


def head_revision() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def schema_state(engine: Engine) -> dict[str, Any]:
    """status: empty | ready | outdated | unmanaged"""
    tables = set(inspect(engine).get_table_names())
    head = head_revision()
    has_version = "alembic_version" in tables
    has_app_tables = bool(APP_TABLES & tables)

    current = None
    if has_version:
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()

    if not has_app_tables and not has_version:
        status = "empty"
    elif has_version and current == head:
        status = "ready"
    elif has_version:
        status = "outdated"
    else:
        status = "unmanaged"  # 테이블은 있는데 alembic 이력이 없다 (마이그레이션 없이 만든 DB)

    return {"status": status, "current": current, "head": head}


# 코드가 기대하는 테이블·컬럼이 DB에 없을 때 Postgres가 돌려주는 오류 코드 (undefined_table, undefined_column)
SCHEMA_ERROR_SQLSTATES = {"42P01", "42703"}

OUTDATED_MESSAGE = (
    "서버 데이터베이스가 최신 버전이 아니라 이 요청을 처리할 수 없습니다. "
    "관리자에게 DB 업데이트(마이그레이션)를 요청해 주세요."
)


def live_state(engine: Engine) -> dict[str, Any]:
    """지금 이 순간의 DB 스키마 상태. 서버 시작 때의 값이 아니라 매번 DB에서 다시 읽는다.

    마이그레이션을 서버가 떠 있는 동안 적용해도 재시작 없이 `ready`로 바뀐다.
    """
    try:
        return schema_state(engine)
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__, "current": None, "head": None}


def is_schema_mismatch(exc: BaseException) -> bool:
    """예외(또는 그 원인)가 '없는 테이블/컬럼을 조회했다'는 DB 오류인가."""
    seen: set[int] = set()
    current: BaseException | None = exc

    while current is not None and id(current) not in seen:
        seen.add(id(current))

        if isinstance(current, DBAPIError):
            sqlstate = getattr(current.orig, "sqlstate", None) or getattr(current.orig, "pgcode", None)
            if sqlstate in SCHEMA_ERROR_SQLSTATES:
                return True

        current = current.__cause__ or current.__context__

    return False


def outdated_by(exc: BaseException, engine: Engine) -> bool:
    """이 오류의 원인이 'DB가 코드보다 뒤처져 있기 때문'이라고 확신할 수 있는가.

    스키마 불일치 오류이면서 지금 DB가 실제로 최신이 아닐 때만 True. (그 외의 같은 코드 오류는 일반 오류로 둔다)
    """
    return is_schema_mismatch(exc) and live_state(engine)["status"] != "ready"


def upgrade_head(engine: Engine | None = None) -> None:
    command.upgrade(alembic_config(engine), "head")


def ensure_schema(
    engine: Engine,
    upgrade: Callable[[Engine], None] = upgrade_head,
) -> dict[str, Any]:
    """Postgres 서버 시작 시 호출. 예외를 던지지 않고 상태 dict를 돌려준다."""
    try:
        state = schema_state(engine)

        if state["status"] == "empty":
            # 트랜잭션 단위 advisory lock: 풀러(Supabase 6543 등)를 거쳐도 새지 않고, 트랜잭션이 끝나면 풀린다.
            # 마이그레이션은 별도 연결에서 실행하며, 이 트랜잭션이 끝나기 전까지 다른 프로세스를 기다리게 한다.
            with engine.begin() as lock:
                lock.execute(text("SET LOCAL lock_timeout = '60s'"))
                lock.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": ADVISORY_LOCK_ID})

                state = schema_state(engine)  # 잠금을 기다리는 사이 다른 프로세스가 만들었을 수 있다
                if state["status"] == "empty":
                    logger.warning("빈 데이터베이스입니다. 마이그레이션을 처음 적용합니다.")
                    upgrade(engine)
                    state = {**schema_state(engine), "migrated": True}

        if state["status"] == "outdated":
            logger.error(
                "DB 마이그레이션이 필요합니다 (DB %s, 코드 %s). 자동으로 바꾸지 않습니다. "
                "`cd backend && python -m scripts.migrate --upgrade` 를 실행하세요.",
                state["current"], state["head"],
            )
        elif state["status"] == "unmanaged":
            logger.error(
                "테이블은 있는데 alembic 이력(alembic_version)이 없습니다. 마이그레이션 없이 만든 DB로 보입니다. "
                "자동으로 바꾸지 않습니다. 담당자에게 문의하세요."
            )
        return state

    except Exception as exc:  # DB 연결 실패 등. 서버는 계속 뜬다.
        logger.exception("DB 스키마 상태를 확인하지 못했습니다")
        return {"status": "error", "error": type(exc).__name__, "current": None, "head": None}
