import pytest

from app.config import env_str, load_settings, read_bool


@pytest.mark.parametrize("name", ["DATABASE_URL", "MAX_UPLOAD_MB", "REGISTRATION_MAX_UPLOAD_MB",
                                  "FRONTEND_ORIGINS", "ANTHROPIC_MODEL", "UPLOAD_DIR", "SUPABASE_STORAGE_BUCKET"])
def test_empty_value_means_default(monkeypatch, name):
    """.env.example을 복사한 직후처럼 `KEY=`가 비어 있어도 서버가 뜨고 기본값을 쓴다."""
    monkeypatch.delenv(name, raising=False)  # 개발자 PC의 .env 값에 영향받지 않게 '미설정'을 기준으로 삼는다
    baseline = load_settings()
    monkeypatch.setenv(name, "")
    assert load_settings() == baseline


def test_empty_database_url_falls_back_to_sqlite(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "   ")
    assert load_settings().database_url.startswith("sqlite")


def test_empty_bool_uses_default_not_false(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "")
    monkeypatch.setenv("LEGAL_CITATIONS_ENABLED", "")
    assert read_bool("DEMO_MODE", True) is True
    assert load_settings().legal_citations_enabled is True


def test_explicit_values_still_win(monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "7")
    monkeypatch.setenv("DEMO_MODE", "false")
    s = load_settings()
    assert s.max_upload_bytes == 7 * 1024 * 1024 and s.demo_mode is False
    assert env_str("NO_SUCH_KEY_X", "dflt") == "dflt"
