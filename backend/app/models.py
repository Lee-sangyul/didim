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
    citations: str = "[]"

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

class RegistrationApplication(SQLModel, table=True):
    """
    교직원 계정 발급 신청 정보.

    신청 단계에서는 User 계정을 만들지 않는다.
    관리자가 승인했을 때만 실제 User 계정이 생성된다.
    """

    __tablename__ = "registration_applications"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    username: str = Field(index=True)
    password_hash: str

    name: str
    school_name: str = Field(index=True)
    email: str = Field(index=True)
    phone: Optional[str] = None

    # pending / approved / rejected
    status: str = Field(
        default="pending",
        index=True,
    )

    rejection_reason: Optional[str] = None

    reviewed_by: Optional[int] = Field(
        default=None,
        foreign_key="users.id",
        index=True,
    )

    reviewed_at: Optional[str] = Field(
        default=None,
        index=True,
    )

    document_delete_after: Optional[str] = Field(
        default=None,
        index=True,
    )

    created_at: str = Field(
        default_factory=now_iso,
        index=True,
    )

    updated_at: str = Field(
        default_factory=now_iso,
    )


class RegistrationDocument(SQLModel, table=True):
    """
    회원가입 신청 시 제출한 증빙 문서 정보.

    실제 파일은 DB에 넣지 않고 비공개 저장소에 보관한다.
    DB에는 파일 위치와 검증용 해시만 저장한다.
    """

    __tablename__ = "registration_documents"

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
    )

    application_id: int = Field(
        foreign_key="registration_applications.id",
        index=True,
    )

    original_filename: str

    storage_path: str = Field(
        unique=True,
        index=True,
    )

    content_type: str
    size: int

    sha256: str = Field(index=True)

    created_at: str = Field(
        default_factory=now_iso,
    )

    deleted_at: Optional[str] = Field(
        default=None,
        index=True,
    )