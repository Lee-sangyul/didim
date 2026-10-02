"""후보 조문 중 근거를 고른다. LLM은 article_id와 이유만 반환하고,
조문 원문은 항상 DB에서 꺼내 붙인다."""
import json
import logging
import re
from typing import Any, Optional

from sqlmodel import Session

from .config import MAX_SELECTED
from .models import Article, Law
from .schemas import Citation

logger = logging.getLogger(__name__)

SELECTOR_SYSTEM = (
    "당신은 교권 침해 상담 사례에 참고할 법조문을 고르는 도우미입니다. "
    "후보 목록에 있는 article_id만 선택하세요. 관련이 약하면 적게 고르거나 하나도 고르지 마세요. "
    f"최대 {MAX_SELECTED}개까지 고르고, 각 선택 이유는 한 문장으로 쓰세요. "
    "법률 판단을 확정하지 말고, 조문 내용을 새로 쓰지 마세요. "
    '출력은 JSON 하나만: {"selected": [{"article_id": 12, "reason": "..."}]}'
)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```\s*$", "", text)
    return text.strip()


def _format_candidates(candidates: list[Article], law_names: dict[int, str]) -> str:
    blocks = []
    for a in candidates:
        blocks.append(
            f"[article_id={a.id}] {law_names.get(a.law_id, '')} {a.article_no}"
            f" {a.title or ''}\n{a.body}"
        )
    return "\n\n".join(blocks)


def parse_selection(raw: str, candidate_ids: set[int]) -> list[dict[str, Any]]:
    """LLM 출력 JSON을 파싱하고, 후보에 없는 id·중복·형식 오류는 버린다."""
    data = json.loads(_strip_code_fence(raw))
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for item in data.get("selected", []):
        try:
            article_id = int(item["article_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if article_id not in candidate_ids or article_id in seen:
            continue
        seen.add(article_id)
        result.append(
            {"article_id": article_id, "reason": str(item.get("reason", "")).strip()}
        )
        if len(result) >= MAX_SELECTED:
            break
    return result


def select_citations(
    client: Any,
    model: str,
    case_summary: str,
    candidates: list[Article],
    session: Session,
) -> list[Citation]:
    """실패하면 예외 대신 빈 리스트를 반환한다 (기존 기능을 막지 않는다)."""
    if not candidates:
        return []
    try:
        law_names: dict[int, str] = {}
        laws: dict[int, Law] = {}
        for a in candidates:
            if a.law_id not in laws:
                law = session.get(Law, a.law_id)
                if law is not None:
                    laws[a.law_id] = law
                    law_names[a.law_id] = law.name

        response = client.messages.create(
            model=model,
            max_tokens=800,
            system=SELECTOR_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"## 사건 요약\n{case_summary}\n\n"
                        f"## 후보 조문\n{_format_candidates(candidates, law_names)}"
                    ),
                }
            ],
        )
        raw = "".join(b.text for b in response.content if b.type == "text")
        picked = parse_selection(raw, {a.id for a in candidates if a.id is not None})

        by_id = {a.id: a for a in candidates}
        citations: list[Citation] = []
        for item in picked:
            article = by_id[item["article_id"]]
            law = laws.get(article.law_id)
            if law is None:
                continue
            citations.append(
                Citation(
                    article_id=article.id,  # type: ignore[arg-type]
                    law_name=law.name,
                    article_no=article.article_no,
                    title=article.title,
                    text=article.body,
                    reason=item["reason"],
                    source_url=law.source_url,
                    as_of=law.fetched_at.date().isoformat(),
                )
            )
        return citations
    except Exception:
        logger.exception("legal selector failed; falling back to no citations")
        return []
