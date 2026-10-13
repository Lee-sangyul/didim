"""법령 검색 DB(legal.db)를 articles.json으로부터 자동으로 준비한다.

배포 절차: **`data/legal/articles.json`만 함께 배포하면 된다.**
legal.db는 git·배포물에 넣지 않는 생성물이고, 서버가 시작할 때 이 함수가
없거나 articles.json과 내용이 다르면 다시 만든다 (별도 복원 명령을 잊어도 근거 조문이 사라지지 않는다).

- 같은 articles.json이면 아무것도 하지 않는다(내용 해시를 DB에 기록).
- articles.json이 바뀌면 전체를 교체한다(없어진 법령이 남지 않게).
- 실패해도 서버 시작을 막지 않는다(근거 조문만 빠짐). 상태는 /api/health의 legal 항목으로 확인한다.
"""
import hashlib
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, delete

from . import ingest, retriever
from .config import ARTICLES_JSON
from .db import legal_engine, legal_registry
from .models import Article, Law

logger = logging.getLogger(__name__)

_META_DDL = "CREATE TABLE IF NOT EXISTS legal_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _counts(session: Session) -> tuple[int, int]:
    try:
        laws = session.exec(text("SELECT count(*) FROM law")).scalar_one()  # type: ignore[call-overload]
        articles = session.exec(text("SELECT count(*) FROM article")).scalar_one()  # type: ignore[call-overload]
        return int(laws), int(articles)
    except Exception:
        return 0, 0  # 테이블이 아직 없다


def _stored_digest(session: Session) -> str | None:
    try:
        row = session.exec(text("SELECT value FROM legal_meta WHERE key='articles_sha256'")).first()  # type: ignore[call-overload]
    except Exception:
        return None
    return row[0] if row else None


def ensure_legal_db(
    engine: Engine | None = None,
    articles_path: Path | None = None,
) -> dict[str, Any]:
    """상태를 돌려준다: status = ready | rebuilt | missing_source | error."""
    engine = engine or legal_engine
    path = articles_path or ARTICLES_JSON

    try:
        with Session(engine) as session:
            laws, articles = _counts(session)

            if not path.exists():
                status = "ready" if articles else "missing_source"
                return {"status": status, "laws": laws, "articles": articles, "source": str(path.name)}

            digest = _digest(path)

            if articles and _stored_digest(session) == digest:
                return {"status": "ready", "laws": laws, "articles": articles}

            legal_registry.metadata.create_all(engine)
            session.exec(delete(Article))  # type: ignore[call-overload]
            session.exec(delete(Law))  # type: ignore[call-overload]
            session.commit()

            ingest.load_from_json(session, path)
            session.commit()
            retriever.rebuild_index(session)

            session.exec(text(_META_DDL))  # type: ignore[call-overload]
            session.exec(  # type: ignore[call-overload]
                text("INSERT OR REPLACE INTO legal_meta(key, value) VALUES ('articles_sha256', :v)"),
                params={"v": digest},
            )
            session.commit()

            laws, articles = _counts(session)
            logger.info("legal db rebuilt from %s: %s laws, %s articles", path.name, laws, articles)
            return {"status": "rebuilt", "laws": laws, "articles": articles}

    except Exception as exc:
        logger.exception("legal db bootstrap failed")
        return {"status": "error", "laws": 0, "articles": 0, "error": type(exc).__name__}
