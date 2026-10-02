"""조문 검색. 외부에서는 search()만 사용한다 (내부 구현 교체 가능).

점수 계산
1. 검색어(query)를 공백으로 나눈 단어(term)마다 조문별 원점수를 구한다.
   - 3글자 이상: FTS5 trigram + bm25 (조 제목 열에 가중치 TITLE_WEIGHT)
   - 3글자 미만: trigram이 매칭하지 못하므로 LIKE로 제목·본문 등장 횟수를 센다.
2. 단어별 원점수를 최댓값으로 나눠 0~1로 맞춘 뒤 IDF(희소할수록 큼)를 곱한다.
   bm25와 LIKE 횟수는 척도가 달라서, 정규화 없이 더하면 3글자 이상 단어가 항상 이긴다.
   여러 단어 검색어는 두 가지 가점을 더한다.
   - 구문 가점: 검색어가 띄어쓰기까지 그대로 제목·본문에 나오면 단어 하나 몫을 더한다.
   - 제목 가점: 조 제목에 모든 단어가 들어 있으면, 제목에서 검색어가 차지하는 비율만큼 더한다.
     "(교육활동 침해행위)"처럼 제목이 곧 검색어인 정의 조문이, 같은 단어를 본문에서
     더 자주 쓰는 다른 조문보다 앞서게 하기 위해서다. (단어 하나짜리 검색어에도 적용)
3. 검색어별로 순위를 매기고, 검색어들을 번갈아 가며(라운드 로빈) 상위 결과를 고른다.
   검색어 하나("교육활동 침해행위")가 흔한 단어로 상위 k개를 독차지해
   다른 검색어("폭행")의 결과가 밀려나는 것을 막는다.

FTS 색인에는 법령명을 넣지 않는다. 법령명을 넣으면 '아동학대', '교육활동' 같은 단어가
그 법령의 모든 조문에 매칭되어 점수가 왜곡된다.
"""
import math
import re
from collections import defaultdict
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session, select

from .db import legal_engine
from .config import CANDIDATE_K
from .models import Article

ARTICLE_NO_RE = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")

TITLE_WEIGHT = 3.0  # 조 제목에 나온 단어는 본문보다 강한 신호
LIKE_BODY_CAP = 5  # LIKE 경로에서 본문 등장 횟수 상한
TITLE_MATCH_BONUS = 2.0  # 제목 가점 배율 (검색어 전체 IDF 합 기준)
_TITLE_NOISE_RE = re.compile(r"[\s()ㆍ·,]")

_FTS_DDL = (
    "CREATE VIRTUAL TABLE article_fts "
    "USING fts5(title, body, tokenize='trigram')"
)


def rebuild_index(session: Session) -> int:
    """article 테이블 전체로 FTS 인덱스를 다시 만든다. 색인한 건수를 반환.

    열 구성이 바뀔 수 있으므로 기존 테이블을 지우고 새로 만든다.
    """
    session.exec(text("DROP TABLE IF EXISTS article_fts"))  # type: ignore[call-overload]
    session.exec(text(_FTS_DDL))  # type: ignore[call-overload]
    session.exec(  # type: ignore[call-overload]
        text(
            "INSERT INTO article_fts(rowid, title, body) "
            "SELECT id, coalesce(title, ''), body FROM article"
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
    """단어 하나에 대한 조문별 원점수(클수록 관련). 척도는 경로마다 다르다."""
    if len(term) >= 3:
        phrase = '"' + term.replace('"', '""') + '"'
        rows = session.exec(  # type: ignore[call-overload]
            text(
                "SELECT rowid, bm25(article_fts, :tw, 1.0) FROM article_fts "
                "WHERE article_fts MATCH :q"
            ),
            params={"q": phrase, "tw": TITLE_WEIGHT},
        ).all()
        return {int(rid): -float(score) for rid, score in rows}
    pattern = f"%{_escape_like(term)}%"
    rows = session.exec(  # type: ignore[call-overload]
        text(
            "SELECT id, coalesce(title, ''), body FROM article "
            "WHERE title LIKE :p ESCAPE '\\' OR body LIKE :p ESCAPE '\\'"
        ),
        params={"p": pattern},
    ).all()
    return {
        int(rid): TITLE_WEIGHT * title.count(term) + min(body.count(term), LIKE_BODY_CAP)
        for rid, title, body in rows
    }


def _query_scores(session: Session, query: str, total: int) -> dict[int, float]:
    """검색어 하나의 조문별 점수 = Σ(단어별 정규화 점수 × IDF) + 구문·제목 가점."""
    terms = list(dict.fromkeys(query.split()))  # 순서 유지 중복 제거
    scores: dict[int, float] = defaultdict(float)
    weight_sum = 0.0
    for term in terms:
        raw = _term_scores(session, term)
        if not raw:
            continue
        top = max(raw.values())
        if top <= 0:
            continue
        idf = math.log(1 + total / len(raw))
        weight_sum += idf
        for article_id, score in raw.items():
            scores[article_id] += idf * score / top
    if not scores:
        return {}

    if len(terms) > 1:
        rows = session.exec(  # type: ignore[call-overload]
            text(
                "SELECT id FROM article "
                "WHERE title LIKE :p ESCAPE '\\' OR body LIKE :p ESCAPE '\\'"
            ),
            params={"p": f"%{_escape_like(' '.join(terms))}%"},
        ).all()
        for (article_id,) in rows:
            if article_id in scores:
                scores[article_id] += weight_sum / len(terms)

    term_len = sum(len(t) for t in terms)
    rows = session.exec(
        select(Article.id, Article.title).where(Article.id.in_(list(scores)))  # type: ignore[union-attr]
    ).all()
    for article_id, title in rows:
        if title and all(t in title for t in terms):
            core = _TITLE_NOISE_RE.sub("", title)
            coverage = min(1.0, term_len / len(core)) if core else 0.0
            scores[article_id] += TITLE_MATCH_BONUS * weight_sum * coverage
    return scores


def search(
    queries: list[str],
    k: int = CANDIDATE_K,
    session: Optional[Session] = None,
) -> list[Article]:
    """여러 검색어 결과를 합쳐 중복 제거 후 상위 k개를 반환한다.

    조문번호가 명시된 검색어는 메타데이터로 직접 조회해 맨 앞에 둔다.
    """
    own = session is None
    session = session or Session(legal_engine)
    try:
        total = session.exec(text("SELECT count(*) FROM article")).scalar_one()  # type: ignore[call-overload]
        direct: list[int] = []
        ranked_lists: list[list[tuple[float, int]]] = []

        for query in queries:
            query = query.strip()
            if not query:
                continue

            for match in ARTICLE_NO_RE.finditer(query):
                no = _normalize_article_no(match)
                ids = session.exec(
                    select(Article.id).where(Article.article_no == no)
                ).all()
                direct.extend(i for i in ids if i is not None and i not in direct)
            query = ARTICLE_NO_RE.sub(" ", query)

            scores = _query_scores(session, query, total)
            if scores:
                top = max(scores.values())
                ranked_lists.append(
                    sorted(((s / top, i) for i, s in scores.items()), key=lambda x: (-x[0], x[1]))
                )

        # 라운드 로빈: 각 검색어의 r위 결과를 모아 (상대 점수 순으로) 차례로 채운다.
        ordered = list(direct)
        seen = set(ordered)
        depth = max((len(r) for r in ranked_lists), default=0)
        for r in range(depth):
            if len(ordered) >= k:
                break
            bucket = sorted(
                (lst[r] for lst in ranked_lists if r < len(lst)),
                key=lambda x: (-x[0], x[1]),
            )
            for _, article_id in bucket:
                if article_id not in seen:
                    seen.add(article_id)
                    ordered.append(article_id)
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
