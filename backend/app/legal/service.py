"""파이프라인 진입점: 분석 결과 -> 검색어 -> 후보 -> 근거 선택 -> citations."""
import logging
from typing import Any, Optional

from sqlmodel import Session

from ..config import settings
from .db import legal_engine
from . import retriever
from .config import CANDIDATE_K, MAX_QUERIES
from .schemas import Citation
from .selector import select_citations

logger = logging.getLogger(__name__)


def build_queries(category: str, keywords: Optional[list[str]] = None) -> list[str]:
    """침해 유형·키워드로 검색어 1~4개를 만든다. 사용자 입력 원문은 쓰지 않는다."""
    queries: list[str] = []
    if category.strip() == "일반 상담":
        category = ""
    parts = [*category.replace("·", " ").split(), *(keywords or [])]
    for item in parts:
        item = (item or "").strip()
        if item and item not in queries:
            queries.append(item)
    return queries[:MAX_QUERIES]


def find_citations(
    client: Any,
    model: str,
    category: str,
    case_summary: str,
    keywords: Optional[list[str]] = None,
) -> list[Citation]:
    """어떤 실패도 예외로 전파하지 않는다. 플래그가 꺼져 있으면 빈 리스트."""
    if not settings.legal_citations_enabled:
        return []
    try:
        queries = build_queries(category, keywords)
        if not queries:
            return []
        with Session(legal_engine) as session:
            candidates = retriever.search(queries, CANDIDATE_K, session=session)
            return select_citations(client, model, case_summary, candidates, session)
    except Exception:
        logger.exception("legal citation lookup failed")
        return []
