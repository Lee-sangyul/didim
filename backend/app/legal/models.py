from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field

from .db import LegalModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Law(LegalModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    law_mst: str
    promulgation_no: Optional[str] = None
    effective_date: Optional[str] = None  # YYYY-MM-DD
    source_url: str
    fetched_at: datetime = Field(default_factory=_utcnow)


class Article(LegalModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    law_id: int = Field(foreign_key="law.id", index=True)
    article_no: str  # "제15조", "제15조의2"
    title: Optional[str] = None
    body: str
    search_text: str
