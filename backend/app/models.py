from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Case(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = "새 상담"
    category: str = "분석 중"
    risk_level: str = "low"
    risk_score: int = 0
    based_law: str = "[]"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True, foreign_key="case.id")
    role: str
    content: str
    created_at: str = Field(default_factory=now_iso)


class Assessment(SQLModel, table=True):
    """History of every per-turn risk assessment for a case, including the
    law provisions that were used as the basis for that turn's judgment."""

    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True, foreign_key="case.id")
    message_id: Optional[int] = Field(default=None, foreign_key="message.id")
    risk_level: str = "low"
    risk_score: int = 0
    category: str = ""
    rationale: str = ""
    based_law: str = "[]"
    actions: str = "[]"
    created_at: str = Field(default_factory=now_iso)


class Attachment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    case_id: int = Field(index=True, foreign_key="case.id")
    filename: str
    stored_name: str
    content_type: str = "application/octet-stream"
    size: int = 0
    created_at: str = Field(default_factory=now_iso)

