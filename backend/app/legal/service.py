"""파이프라인 진입점: 분석 결과 -> 검색어 -> 후보 -> 근거 선택 -> citations."""
import json
import logging
from typing import Any, Optional

from sqlmodel import Session

from ..config import settings
from .db import legal_engine
from . import retriever
from .config import CANDIDATE_K, MAX_QUERIES
from .schemas import Citation
from .selector import _strip_code_fence, select_citations

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


QUERY_SYSTEM = (
    "교권 침해 상담 사례에서 법령 조문 검색에 쓸 한국어 검색어를 만드세요. "
    "법령 본문에 실제로 나올 법한 명사 형태의 용어(예: 교육활동 침해행위, 아동학대, 신고의무, "
    "보호조치, 교권보호위원회)로 1~4개를 고르고, 사례 원문이나 개인정보를 그대로 쓰지 마세요. "
    '출력은 JSON 하나만: {"queries": ["...", "..."]}'
)


def generate_queries(client: Any, model: str, category: str, case_summary: str) -> list[str]:
    """LLM으로 법령 용어 검색어를 만든다. 실패하면 분석 결과 기반 검색어로 폴백한다."""
    fallback = build_queries(category)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=200,
            system=QUERY_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": f"분석 유형: {category}\n사례: {case_summary}",
                }
            ],
        )
        raw = "".join(b.text for b in response.content if b.type == "text")
        queries = [
            str(q).strip()
            for q in json.loads(_strip_code_fence(raw)).get("queries", [])
            if str(q).strip()
        ]
        return queries[:MAX_QUERIES] or fallback
    except Exception:
        logger.exception("legal query generation failed; using fallback queries")
        return fallback


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
        queries = generate_queries(client, model, category, case_summary)
        if keywords:
            queries = build_queries(" ".join(queries), keywords)
        if not queries:
            return []
        with Session(legal_engine) as session:
            candidates = retriever.search(queries, CANDIDATE_K, session=session)
            return select_citations(client, model, case_summary, candidates, session)
    except Exception:
        logger.exception("legal citation lookup failed")
        return []
