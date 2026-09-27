import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional


SESSION_COOKIE_NAME = "didim_session"
SESSION_DURATION_DAYS = 7


def create_session_token() -> str:
    """
    브라우저 쿠키에 저장할 무작위 세션 토큰을 생성한다.

    이 원본 토큰은 브라우저에만 전달하고
    데이터베이스에는 직접 저장하지 않는다.
    """
    return secrets.token_urlsafe(48)


def hash_session_token(token: str) -> str:
    """
    세션 토큰을 SHA-256으로 해시한다.

    데이터베이스에는 이 함수의 결과만 저장한다.
    """
    if not token:
        raise ValueError("세션 토큰은 비어 있을 수 없습니다.")

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_session_expiry() -> str:
    """
    현재 시각을 기준으로 세션 만료 시각을 생성한다.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=SESSION_DURATION_DAYS
    )

    return expires_at.isoformat()


def is_session_expired(
    expires_at: str,
    current_time: Optional[datetime] = None,
) -> bool:
    """
    저장된 세션 만료 시각이 지났는지 확인한다.
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    expiry_time = datetime.fromisoformat(expires_at)

    if expiry_time.tzinfo is None:
        expiry_time = expiry_time.replace(
            tzinfo=timezone.utc
        )

    return current_time >= expiry_time