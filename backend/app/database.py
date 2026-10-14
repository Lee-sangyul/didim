from collections.abc import Generator

from sqlmodel import Session, create_engine

from .config import ROOT, settings


database_url = settings.database_url
connect_args: dict = {}


# SQLite를 사용할 때만 적용할 설정
if settings.is_sqlite:
    connect_args["check_same_thread"] = False

    # 기본 상대경로를 프로젝트 기준 절대경로로 변경
    if database_url == "sqlite:///./data/didim.db":
        database_path = (
            ROOT / "data" / "didim.db"
        ).resolve()

        database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        database_url = (
            f"sqlite:///{database_path.as_posix()}"
        )


# 실제 데이터베이스 연결 엔진
engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)


def get_session() -> Generator[Session, None, None]:
    """
    FastAPI 요청마다 DB 세션을 만들고,
    요청이 끝나면 자동으로 닫는다.
    """
    with Session(engine) as session:
        yield session

def init_sqlite_schema() -> None:
    """
    SQLite 로컬 실행 시 테이블을 만들고, 이후 추가된 컬럼을 보충한다.

    Postgres(운영)는 alembic 마이그레이션이 담당하므로 호출하지 않는다.
    """
    from sqlmodel import SQLModel

    from . import models  # noqa: F401  (테이블 등록)

    SQLModel.metadata.create_all(engine)

    # (테이블, 컬럼, DDL) - alembic을 거치지 않는 기존 SQLite 파일을 위한 보충
    added_columns = [
        ("case", "based_law", "VARCHAR DEFAULT '[]'"),
        ("assessment", "citations", "VARCHAR DEFAULT '[]'"),
        ("message", "versions", "VARCHAR DEFAULT '[]'"),
    ]

    with engine.connect() as conn:
        for table, column, ddl in added_columns:
            existing = {
                row[1]
                for row in conn.exec_driver_sql(
                    f'PRAGMA table_info("{table}")'
                ).fetchall()
            }

            if column not in existing:
                conn.exec_driver_sql(
                    f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl}'
                )
                conn.commit()
