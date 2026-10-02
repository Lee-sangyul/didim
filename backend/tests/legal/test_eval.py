"""검색·선택 품질 채점 (수치 확인용, 임계값으로 실패시키지 않는다).

기대 조문이 채워진 사례만 채점한다. 실행: pytest tests/legal/test_eval.py -s
selector 실호출 평가는 `-m live` (ANTHROPIC_API_KEY 필요).
"""
import json
from pathlib import Path

import pytest
from sqlmodel import Session

from app.config import settings
from app.legal.db import legal_engine
from app.legal import retriever
from app.legal.config import CANDIDATE_K
from app.legal.models import Article, Law
from app.legal.service import find_citations

CASES = json.loads((Path(__file__).parent / "eval_cases.json").read_text("utf-8"))["cases"]
GRADED = [c for c in CASES if c.get("expected_articles")]


def _key(law: str, no: str) -> tuple[str, str]:
    return (law, no)


def _hits(session: Session, articles: list[Article]) -> set[tuple[str, str]]:
    result = set()
    for a in articles:
        law = session.get(Law, a.law_id)
        if law:
            result.add(_key(law.name, a.article_no))
    return result


def _print_table(rows: list[tuple[str, str]], title: str) -> None:
    print(f"\n{title}")
    for case_id, mark in rows:
        print(f"  {case_id:<14}{mark}")
    if rows:
        ok = sum(m == "O" for _, m in rows)
        print(f"  => {ok}/{len(rows)}")


@pytest.mark.skipif(not GRADED, reason="expected_articles가 채워진 사례가 없음")
def test_retriever_recall():
    rows = []
    with Session(legal_engine) as session:
        for c in GRADED:
            found = _hits(session, retriever.search(c["queries"], CANDIDATE_K, session=session))
            expected = {_key(e["law"], e["article_no"]) for e in c["expected_articles"]}
            rows.append((c["id"], "O" if expected <= found else "X"))
    _print_table(rows, f"retriever recall@{CANDIDATE_K}")


@pytest.mark.live
@pytest.mark.skipif(not GRADED, reason="expected_articles가 채워진 사례가 없음")
def test_selector_hit():
    from anthropic import Anthropic

    client = Anthropic(api_key=settings.anthropic_api_key)
    rows = []
    for c in GRADED:
        citations = find_citations(client, settings.anthropic_model, " ".join(c["queries"]), c["input"])
        got = {_key(x.law_name, x.article_no) for x in citations}
        expected = {_key(e["law"], e["article_no"]) for e in c["expected_articles"]}
        rows.append((c["id"], "O" if expected & got else "X"))
    _print_table(rows, "selector hit")
