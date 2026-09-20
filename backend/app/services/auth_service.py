from typing import Optional

from sqlmodel import Session, select

from ..models import (
    AuthSession,
    User,
    now_iso,
)
from ..security.password import verify_password
from ..security.session import (
    create_session_expiry,
    create_session_token,
    hash_session_token,
    is_session_expired,
)


def normalize_username(username: str) -> str:
    """
    사용자 이름 앞뒤 공백을 제거하고 소문자로 통일한다.
    """
    return username.strip().lower()


def authenticate_user(
    session: Session,
    username: str,
    password: str,
) -> Optional[User]:
    """
    아이디와 비밀번호를 확인한다.

    로그인 실패 원인을 외부에 구분해서 알려주지 않기 위해
    사용자가 없거나 비밀번호가 틀린 경우 모두 None을 반환한다.
    """
    normalized_username = normalize_username(username)

    user = session.exec(
        select(User).where(
            User.username == normalized_username
        )
    ).first()

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user


def create_auth_session(
    session: Session,
    user: User,
) -> str:
    """
    로그인 세션을 만들고 브라우저에 전달할 원본 토큰을 반환한다.

    데이터베이스에는 토큰의 SHA-256 해시만 저장한다.
    """
    if user.id is None:
        raise ValueError(
            "저장되지 않은 사용자의 세션을 만들 수 없습니다."
        )

    token = create_session_token()
    token_hash = hash_session_token(token)
    current_time = now_iso()

    auth_session = AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=create_session_expiry(),
        created_at=current_time,
        last_used_at=current_time,
    )

    user.last_login_at = current_time

    session.add(auth_session)
    session.add(user)
    session.commit()

    return token


def get_user_from_session_token(
    session: Session,
    token: str,
) -> Optional[User]:
    """
    쿠키의 세션 토큰을 확인하고 로그인 사용자를 반환한다.
    """
    if not token:
        return None

    token_hash = hash_session_token(token)

    auth_session = session.exec(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash
        )
    ).first()

    if auth_session is None:
        return None

    if auth_session.revoked_at is not None:
        return None

    if is_session_expired(auth_session.expires_at):
        return None

    user = session.get(
        User,
        auth_session.user_id,
    )

    if user is None:
        return None

    if not user.is_active:
        return None

    auth_session.last_used_at = now_iso()
    session.add(auth_session)
    session.commit()

    return user


def revoke_auth_session(
    session: Session,
    token: str,
) -> bool:
    """
    로그아웃할 세션을 폐기한다.
    """
    if not token:
        return False

    token_hash = hash_session_token(token)

    auth_session = session.exec(
        select(AuthSession).where(
            AuthSession.token_hash == token_hash
        )
    ).first()

    if auth_session is None:
        return False

    if auth_session.revoked_at is None:
        auth_session.revoked_at = now_iso()
        session.add(auth_session)
        session.commit()

    return True