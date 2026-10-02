"""조문 검색. 외부에서는 search()만 사용한다 (내부 구현 교체 가능).

SQLite FTS5 trigram 토크나이저는 3글자 미만 검색어를 매칭하지 못한다.
("폭언" 같은 2글자 단어) 그래서 3글자 미만 검색어는 LIKE로 처리한다.
"""
import re
from collections import defaultdict
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session, select

from .db import legal_engine
from .config import CANDIDATE_K
from .models import Article

ARTICLE_NO_RE = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")

_FTS_DDL = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS article_fts "
    "USING fts5(search_text, tokenize='trigram')"
)


def rebuild_index(session: Session) -> int:
    """article 테이블 전체로 FTS 인덱스를 다시 만든다. 색인한 건수를 반환."""
    session.exec(text(_FTS_DDL))  # type: ignore[call-overload]
    session.exec(text("DELETE FROM article_fts"))  # type: ignore[call-overload]
    session.exec(  # type: ignore[call-overload]
        text(
            "INSERT INTO article_fts(rowid, search_text) "
            "SELECT id, search_text FROM article"
        )
    )
    session.commit()
    return session.exec(text("SELECT count(*) FROM article_fts")).scalar_one()  # type: ignore[call-overload]


def _normalize_article_no(match: re.Match) -> str:
    no = f"제{match.group(1)}조"
    if match.group(2):
        no += f"의{match.group(2)}"
    return no


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _term_scores(session: Session, term: str) -> dict[int, float]:
    if len(term) >= 3:
        phrase = '"' + term.replace('"', '""') + '"'
        rows = session.exec(  # type: ignore[call-overload]
            text(
                "SELECT rowid, bm25(article_fts) FROM article_fts "
                "WHERE article_fts MATCH :q"
            ),
            params={"q": phrase},
        ).all()
        return {int(rid): -float(score) for rid, score in rows}
    rows = session.exec(  # type: ignore[call-overload]
        text(
            "SELECT id, search_text FROM article "
            "WHERE search_text LIKE :p ESCAPE '\\'"
        ),
        params={"p": f"%{_escape_like(term)}%"},
    ).all()
    return {int(rid): min(float(body.count(term)), 5.0) for rid, body in rows}


def search(
    queries: list[str],
    k: int = CANDIDATE_K,
    session: Optional[Session] = None,
) -> list[Article]:
    """여러 검색어 결과를 합쳐 중복 제거 후 점수 순 상위 k개를 반환한다."""
    own = session is None
    session = session or Session(legal_engine)
    try:
        direct: list[int] = []
        scores: dict[int, float] = defaultdict(float)

        for query in queries:
            query = query.strip()
            if not query:
                continue

            # 조문번호 패턴 -> 메타데이터 직접 조회 우선
            for match in ARTICLE_NO_RE.finditer(query):
                no = _normalize_article_no(match)
                ids = session.exec(
                    select(Article.id).where(Article.article_no == no)
                ).all()
                direct.extend(i for i in ids if i is not None and i not in direct)
            query = ARTICLE_NO_RE.sub(" ", query)

            for term in query.split():
                for article_id, score in _term_scores(session, term).items():
                    scores[article_id] += score

        ranked = [i for i, _ in sorted(scores.items(), key=lambda x: -x[1])]
        ordered = direct + [i for i in ranked if i not in direct]
        ordered = ordered[:k]
        if not ordered:
            return []

        found = {
            a.id: a
            for a in session.exec(select(Article).where(Article.id.in_(ordered)))  # type: ignore[union-attr]
        }
        return [found[i] for i in ordered if i in found]
    finally:
        if own:
            session.close()
