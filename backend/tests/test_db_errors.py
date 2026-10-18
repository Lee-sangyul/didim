"""DB가 코드보다 뒤처졌을 때(R016): 기동은 허용하되 요청 실패는 명확한 503, 복구는 재시작 없이."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import StaticPool

from app import db_errors, db_migrate


def db_error(sqlstate: str) -> DBAPIError:
    orig = type("FakePgError", (Exception,), {"sqlstate": sqlstate})("relation does not exist")
    return DBAPIError("SELECT 1", {}, orig)


@pytest.mark.parametrize("sqlstate, expected", [("42P01", True), ("42703", True), ("23505", False), ("08006", False)])
def test_is_schema_mismatch_uses_sqlstate(sqlstate, expected):
    assert db_migrate.is_schema_mismatch(db_error(sqlstate)) is expected


def test_is_schema_mismatch_follows_cause_chain_and_ignores_other_errors():
    wrapper = RuntimeError("wrapped")
    wrapper.__cause__ = db_error("42P01")
    assert db_migrate.is_schema_mismatch(wrapper) is True
    assert db_migrate.is_schema_mismatch(ValueError("x")) is False


def patch_state(monkeypatch, status):
    monkeypatch.setattr(db_migrate, "live_state", lambda engine: {"status": status, "current": "a", "head": "b"})


def test_outdated_db_gives_503_with_code_and_retry_after(monkeypatch):
    patch_state(monkeypatch, "outdated")
    response = db_errors.outdated_db_response(db_error("42P01"), engine=None)

    assert isinstance(response, JSONResponse) and response.status_code == 503
    assert b'"code":"db_outdated"' in response.body
    assert response.headers["retry-after"] == "60"
    assert "마이그레이션" in response.body.decode()


def test_same_error_on_an_up_to_date_db_stays_a_normal_error(monkeypatch):
    patch_state(monkeypatch, "ready")  # 최신인데 나는 오류는 마이그레이션 문제가 아니다
    assert db_errors.outdated_db_response(db_error("42P01"), engine=None) is None


def test_unrelated_db_error_is_not_masked(monkeypatch):
    patch_state(monkeypatch, "outdated")
    assert db_errors.outdated_db_response(db_error("23505"), engine=None) is None


def test_live_state_reflects_changes_without_restart():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    head = db_migrate.head_revision()
    assert db_migrate.live_state(engine)["status"] == "empty"

    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER)")
        conn.exec_driver_sql("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.exec_driver_sql("INSERT INTO alembic_version VALUES ('0c5eff7e4c9a')")
    assert db_migrate.live_state(engine)["status"] == "outdated"

    with engine.begin() as conn:  # 사람이 서버가 떠 있는 동안 마이그레이션을 적용
        conn.exec_driver_sql(f"UPDATE alembic_version SET version_num = '{head}'")
    assert db_migrate.live_state(engine)["status"] == "ready"


def test_live_state_never_raises():
    assert db_migrate.live_state(create_engine("sqlite:////nonexistent-dir/x.db"))["status"] == "error"


def test_app_handler_returns_503_or_reraises(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "settings", SimpleNamespace(is_sqlite=False))
    exc = db_error("42P01")

    monkeypatch.setattr(main, "outdated_db_response", lambda e, eng: JSONResponse({"detail": "x"}, status_code=503))
    assert asyncio.run(main.handle_db_error(None, exc)).status_code == 503

    monkeypatch.setattr(main, "outdated_db_response", lambda e, eng: None)
    with pytest.raises(DBAPIError):
        asyncio.run(main.handle_db_error(None, exc))  # 일반 오류는 그대로 500 경로로
