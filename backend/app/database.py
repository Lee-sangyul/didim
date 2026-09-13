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