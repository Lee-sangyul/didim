from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class User(SQLModel, table=True):
    """
    디딤에 로그인하는 사용자.

    비밀번호 원문은 저장하지 않고
    password_hash에 해시된 값만 저장한다.
    """

    __tablename__ = "users"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    username: str = Field(
        index=True,
        unique=True,
    )

    password_hash: str
    name: str

    role: str = Field(
        default="teacher",
        index=True,
    )

    is_active: bool = Field(
        default=True,
        index=True,
    )

    created_at: str = Field(
        default_factory=now_iso,
    )

    last_login_at: Optional[str] = Field(
        default=None,
    )


class AuthSession(SQLModel, table=True):
    """
    로그인 상태를 유지하기 위한 서버 세션.

    브라우저에 전달한 세션 토큰 원문은 저장하지 않고
    SHA-256 해시만 token_hash에 저장한다.
    """

    __tablename__ = "auth_sessions"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    user_id: int = Field(
        foreign_key="users.id",
        index=True,
    )

    token_hash: str = Field(
        unique=True,
        index=True,
    )

    expires_at: str = Field(
        index=True,
    )

    created_at: str = Field(
        default_factory=now_iso,
    )

    last_used_at: str = Field(
        default_factory=now_iso,
    )

    revoked_at: Optional[str] = Field(
        default=None,
        index=True,
    )


class Case(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    owner_id: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
    )

    title: str = "새 상담"
    category: str = "분석 중"
    risk_level: str = "low"
    risk_score: int = 0
    based_law: str = "[]"

    created_at: str = Field(
        default_factory=now_iso,
    )

    updated_at: str = Field(
        default_factory=now_iso,
    )


class Message(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    case_id: int = Field(
        index=True,
        foreign_key="case.id",
    )

    role: str
    content: str

    created_at: str = Field(
        default_factory=now_iso,
    )


class Assessment(SQLModel, table=True):
    """
    상담 과정에서 생성된 위험도 평가 이력을 저장한다.

    각 상담 턴마다 위험도, 분류, 판단 근거,
    근거 법령 및 대응 방안을 기록한다.
    """

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    case_id: int = Field(
        index=True,
        foreign_key="case.id",
    )

    message_id: Optional[int] = Field(
        default=None,
        foreign_key="message.id",
    )

    risk_level: str = "low"
    risk_score: int = 0
    category: str = ""
    rationale: str = ""
    based_law: str = "[]"
    actions: str = "[]"

    created_at: str = Field(
        default_factory=now_iso,
    )


class Attachment(SQLModel, table=True):
    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    case_id: int = Field(
        index=True,
        foreign_key="case.id",
    )

    filename: str
    stored_name: str
    content_type: str = "application/octet-stream"
    size: int = 0

    created_at: str = Field(
        default_factory=now_iso,
    )