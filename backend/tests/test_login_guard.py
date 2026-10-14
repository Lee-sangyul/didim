from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import LoginAttempt
from app.services import login_guard as g

T0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def fail(session, user, ip="1.1.1.1", at=T0, times=1):
    state = None
    for i in range(times):
        state = g.record_failure(session, user, ip, now=at + timedelta(seconds=i))
    return state


def test_locks_after_max_failures_and_counts_down(session):
    state = fail(session, "kim", times=g.MAX_FAILURES_PER_USER - 1)
    assert not state.locked and state.remaining == 1

    state = fail(session, "kim", at=T0 + timedelta(seconds=10))
    assert state.locked and state.remaining == 0
    assert 14 * 60 <= state.retry_after <= 15 * 60  # 윈도우 15분

    later = g.check(session, "kim", "1.1.1.1", now=T0 + timedelta(minutes=16))
    assert not later.locked  # 윈도우가 지나면 풀린다


def test_other_user_not_affected_but_same_ip_has_own_limit(session):
    fail(session, "kim", times=g.MAX_FAILURES_PER_USER)
    assert g.check(session, "lee", "2.2.2.2", now=T0 + timedelta(seconds=30)).locked is False

    # 한 IP에서 여러 아이디를 돌려 대입해도 IP 한도에서 막힌다
    for i in range(g.MAX_FAILURES_PER_IP):
        g.record_failure(session, f"user{i}", "9.9.9.9", now=T0 + timedelta(seconds=i))
    assert g.check(session, "brand-new", "9.9.9.9", now=T0 + timedelta(seconds=60)).locked


def test_success_clears_user_failures_and_prunes_old_rows(session):
    fail(session, "kim", times=3)
    g.clear_user(session, "kim")
    assert g.check(session, "kim", "1.1.1.1", now=T0).remaining == g.MAX_FAILURES_PER_USER

    g.record_failure(session, "old", "3.3.3.3", now=T0)
    g.record_failure(session, "new", "3.3.3.3", now=T0 + timedelta(hours=1))
    assert [a.username for a in session.exec(select(LoginAttempt))] == ["new"]  # 오래된 기록은 정리됨
