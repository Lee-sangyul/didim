from typing import Optional

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..legal.schemas import Citation


class CreateCase(BaseModel):
    title: str = "새 상담"


class ChatInput(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class CasePublic(BaseModel):
    id: int
    title: str
    category: str
    risk_level: str
    risk_score: int
    based_law: list[str]
    created_at: str
    updated_at: str


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    role: str
    content: str
    versions: list[str] = []
    created_at: str

    @field_validator("versions", mode="before")
    @classmethod
    def _parse_versions(cls, value):
        # DB에는 JSON 문자열로 저장돼 있다
        if isinstance(value, str):
            try:
                value = json.loads(value or "[]")
            except json.JSONDecodeError:
                return []
        return value if isinstance(value, list) else []


class AssessmentPublic(BaseModel):
    id: int
    case_id: int
    message_id: Optional[int]
    risk_level: str
    risk_score: int
    category: str
    rationale: str
    based_law: list[str]
    actions: list[str]
    citations: list[Citation] = []
    created_at: str


class AttachmentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: int
    filename: str
    content_type: str
    size: int
    created_at: str
