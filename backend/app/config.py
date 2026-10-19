import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")


def env_str(
    name: str,
    default: str = "",
) -> str:
    """환경변수를 읽는다. `KEY=`처럼 비어 있는 값은 설정하지 않은 것으로 보고 기본값을 쓴다.

    .env.example을 복사한 직후에는 값이 빈 키가 많다. 빈 문자열을 그대로 쓰면
    DATABASE_URL=''(엔진 생성 실패)나 MAX_UPLOAD_MB=''(int 변환 실패)처럼 서버가 뜨지 못한다.
    """
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    return value.strip()


def read_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def resolve_path(value: str) -> Path:
    path = Path(value)

    if path.is_absolute():
        return path

    return ROOT / path


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str

    demo_mode: bool
    anthropic_api_key: str
    anthropic_model: str

    frontend_origins: tuple[str, ...]

    upload_dir: Path
    max_upload_bytes: int

    cookie_secure: bool

    supabase_url: str
    supabase_secret_key: str
    supabase_storage_bucket: str

    registration_max_upload_bytes: int

    law_api_oc: str
    legal_citations_enabled: bool

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith(
            "sqlite",
        )

    @property
    def has_supabase_storage(self) -> bool:
        return bool(
            self.supabase_url
            and self.supabase_secret_key
            and self.supabase_storage_bucket
        )


def load_settings() -> Settings:
    origins = tuple(
        origin.strip()
        for origin in env_str(
            "FRONTEND_ORIGINS",
            (
                "http://localhost:5173,"
                "http://127.0.0.1:5173"
            ),
        ).split(",")
        if origin.strip()
    )

    max_upload_mb = int(
        env_str(
            "MAX_UPLOAD_MB",
            "20",
        )
    )

    registration_max_upload_mb = int(
        env_str(
            "REGISTRATION_MAX_UPLOAD_MB",
            "10",
        )
    )

    return Settings(
        app_env=env_str(
            "APP_ENV",
            "development",
        ),
        database_url=env_str(
            "DATABASE_URL",
            "sqlite:///./data/didim.db",
        ),
        demo_mode=read_bool(
            "DEMO_MODE",
            True,
        ),
        anthropic_api_key=env_str(
            "ANTHROPIC_API_KEY",
            "",
        ),
        anthropic_model=env_str(
            "ANTHROPIC_MODEL",
            "claude-sonnet-5",
        ),
        frontend_origins=origins,
        upload_dir=resolve_path(
            env_str(
                "UPLOAD_DIR",
                "./data/uploads",
            )
        ),
        max_upload_bytes=(
            max_upload_mb
            * 1024
            * 1024
        ),
        cookie_secure=read_bool(
            "COOKIE_SECURE",
            False,
        ),
        supabase_url=env_str(
            "SUPABASE_URL",
            "",
        ),
        supabase_secret_key=env_str(
            "SUPABASE_SECRET_KEY",
            "",
        ),
        supabase_storage_bucket=env_str(
            "SUPABASE_STORAGE_BUCKET",
            "registration-documents",
        ),
        registration_max_upload_bytes=(
            registration_max_upload_mb
            * 1024
            * 1024
        ),
        law_api_oc=env_str(
            "LAW_API_OC",
            "",
        ),
        legal_citations_enabled=read_bool(
            "LEGAL_CITATIONS_ENABLED",
            True,
        ),
    )


settings = load_settings()