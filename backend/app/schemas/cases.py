from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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
    created_at: str


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
