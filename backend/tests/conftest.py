"""pytest 전체를 .env·운영 환경과 무관한 격리 환경으로 만든다.

이 파일은 어떤 테스트 모듈보다 먼저 읽히므로, 여기서 환경변수를 정해 두면 `import app...`이
.env의 운영 DB 주소나 실제 API 키를 읽지 못한다(.env는 이미 설정된 값을 덮어쓰지 못한다).

- 데이터베이스·업로드·법령 DB: 임시 폴더 (테스트가 끝나면 지운다)
- 데모 모드, Claude/법제처/Supabase 키는 빈 값 → 외부 호출 불가
- 새 테스트는 별도 설정 없이 `from app.main import app`을 써도 안전하다.
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

TMP = Path(tempfile.mkdtemp(prefix="didim-pytest-"))
atexit.register(lambda: shutil.rmtree(TMP, ignore_errors=True))

# 반드시 app을 import하기 전에 설정한다
os.environ.update(
    APP_ENV="test",
    DATABASE_URL="sqlite:///" + (TMP / "test.db").as_posix(),
    UPLOAD_DIR=str(TMP / "uploads"),
    LEGAL_DATA_DIR=str(TMP / "legal"),
    DEMO_MODE="true",
    ANTHROPIC_API_KEY="",
    LAW_API_OC="",
    SUPABASE_URL="",
    SUPABASE_SECRET_KEY="",
    COOKIE_SECURE="false",
    LOGIN_RATE_LIMIT_ENABLED="true",  # 운영 기본값은 꺼짐(데모용)이지만 기능 코드는 계속 테스트한다
    MAX_UPLOAD_MB="1",  # 용량 초과 테스트를 빠르게 하려고 1MB로 둔다
    LEGAL_CITATIONS_ENABLED="false",
)


@pytest.fixture(scope="session", autouse=True)
def legal_db():
    """법령 검색 DB를 articles.json으로 임시 폴더에 만든다 (개발자 PC의 legal.db에 의존하지 않기 위해)."""
    source = ROOT / "data" / "legal" / "articles.json"
    target = TMP / "legal"
    target.mkdir(parents=True, exist_ok=True)

    if source.exists():
        shutil.copy(source, target / "articles.json")

        from app.legal.bootstrap import ensure_legal_db

        ensure_legal_db()

    yield
