"""법령 전용 SQLite DB (data/legal/legal.db).

메인 DB가 Postgres(Supabase)여도 FTS5 검색을 쓸 수 있도록 분리했다.
읽기 전용 참고 데이터이며 articles.json으로 언제든 다시 만들 수 있다 (git에는 올리지 않음).
"""
from sqlalchemy.orm import registry
from sqlmodel import SQLModel, create_engine

from .config import LEGAL_DATA_DIR

LEGAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

legal_registry = registry()


class LegalModel(SQLModel, registry=legal_registry):
    """Law/Article의 베이스. 별도 metadata라 메인 DB의 create_all/alembic에 섞이지 않는다."""


legal_engine = create_engine(
    f"sqlite:///{(LEGAL_DATA_DIR / 'legal.db').as_posix()}",
    connect_args={"check_same_thread": False},
)
