"""로그인 무차별 대입 방지.

규칙(윈도우 안의 실패 횟수 기준)
- 같은 아이디로 MAX_FAILURES_PER_USER회 실패하면 윈도우가 지나기 전까지 잠근다.
- 같은 IP에서 MAX_FAILURES_PER_IP회 실패하면 그 IP를 잠근다 (여러 아이디를 돌려 대입하는 공격).
- 잠긴 동안에는 비밀번호가 맞아도 거부한다. 성공하면 해당 아이디의 실패 기록을 지운다.

DB에 저장하므로 서버를 재시작하거나 프로세스가 여러 개여도 유지된다.
프런트(frontend/src/loginGuard.ts)도 같은 한도를 미리 적용한다 — 값을 바꾸면 양쪽을 함께 바꾼다.
(리버스 프록시 뒤에서는 request.client.host가 프록시 주소가 될 수 있다. uvicorn --proxy-headers 필요)
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil

from sqlmodel import Session, delete, select

from ..models import LoginAttempt

MAX_FAILURES_PER_USER = 5
MAX_FAILURES_PER_IP = 20
WINDOW_MINUTES = 15


@dataclass
class LockState:
    locked: bool
    retry_after: int  # 잠금이 풀릴 때까지 남은 초
    remaining: int  # 이 아이디로 더 시도할 수 있는 횟수


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    # 마이크로초를 항상 포함해야 문자열 정렬이 시간 순서와 같다
    return value.isoformat(timespec="microseconds")


def _failures(session: Session, column, value: str, since: datetime) -> list[datetime]:
    rows = session.exec(
        select(LoginAttempt.created_at)
        .where(column == value, LoginAttempt.created_at >= _iso(since))
        .order_by(LoginAttempt.created_at)  # type: ignore[arg-type]
    ).all()
    return [datetime.fromisoformat(r) for r in rows]


def _lock_seconds(times: list[datetime], limit: int, now: datetime) -> int:
    """윈도우 안의 실패가 limit회 이상이면 limit번째로 최근 실패가 만료될 때까지의 초."""
    if len(times) < limit:
        return 0
    expires = times[-limit] + timedelta(minutes=WINDOW_MINUTES)
    return max(0, ceil((expires - now).total_seconds()))


def check(session: Session, username: str, ip: str, now: datetime | None = None) -> LockState:
    now = now or _now()
    since = now - timedelta(minutes=WINDOW_MINUTES)
    by_user = _failures(session, LoginAttempt.username, username, since)
    by_ip = _failures(session, LoginAttempt.ip, ip, since)

    retry = max(
        _lock_seconds(by_user, MAX_FAILURES_PER_USER, now),
        _lock_seconds(by_ip, MAX_FAILURES_PER_IP, now),
    )
    return LockState(
        locked=retry > 0,
        retry_after=retry,
        remaining=max(0, MAX_FAILURES_PER_USER - len(by_user)),
    )


def record_failure(session: Session, username: str, ip: str, now: datetime | None = None) -> LockState:
    now = now or _now()
    session.add(LoginAttempt(username=username, ip=ip, created_at=_iso(now)))
    # 윈도우를 벗어난 기록은 더 이상 쓸모없으므로 같이 정리한다(테이블이 커지지 않게)
    session.exec(  # type: ignore[call-overload]
        delete(LoginAttempt).where(
            LoginAttempt.created_at < _iso(now - timedelta(minutes=WINDOW_MINUTES))
        )
    )
    session.commit()
    return check(session, username, ip, now)


def clear_user(session: Session, username: str) -> None:
    session.exec(delete(LoginAttempt).where(LoginAttempt.username == username))  # type: ignore[call-overload]
    session.commit()
