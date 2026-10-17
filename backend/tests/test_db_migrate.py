import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app import db_migrate


@pytest.fixture()
def engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def exec_sql(engine, *statements):
    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))


def test_head_revision_exists_and_is_single():
    assert db_migrate.head_revision()


def test_schema_state_classification(engine):
    head = db_migrate.head_revision()
    assert db_migrate.schema_state(engine)["status"] == "empty"

    exec_sql(engine, 'CREATE TABLE "case" (id INTEGER)')
    assert db_migrate.schema_state(engine)["status"] == "unmanaged"  # 테이블은 있는데 이력이 없다

    exec_sql(
        engine,
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)",
        f"INSERT INTO alembic_version VALUES ('{head}')",
    )
    assert db_migrate.schema_state(engine)["status"] == "ready"

    exec_sql(engine, "UPDATE alembic_version SET version_num = '0c5eff7e4c9a'")  # 첫 리비전
    state = db_migrate.schema_state(engine)
    assert state["status"] == "outdated" and state["current"] == "0c5eff7e4c9a"


def test_ensure_schema_never_changes_an_existing_database(engine):
    exec_sql(
        engine,
        'CREATE TABLE users (id INTEGER)',
        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)",
        "INSERT INTO alembic_version VALUES ('0c5eff7e4c9a')",
    )
    calls = []

    state = db_migrate.ensure_schema(engine, upgrade=lambda _engine: calls.append("upgrade"))

    assert state["status"] == "outdated"
    assert calls == []  # 데이터가 있는 DB는 자동으로 올리지 않는다


def test_ensure_schema_does_not_raise_when_db_unreachable():
    broken = create_engine("sqlite:////nonexistent-dir/x.db")
    assert db_migrate.ensure_schema(broken)["status"] == "error"
