from typing import Optional

from pydantic import BaseModel


class Citation(BaseModel):
    article_id: int
    law_name: str
    article_no: str
    title: Optional[str] = None
    text: str  # DB 원문 (LLM 생성 텍스트 아님)
    reason: str  # LLM이 쓴 선택 이유 (원문과 구분해서 표시)
    source_url: str
    as_of: str  # 수집 기준일 YYYY-MM-DD
