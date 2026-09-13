import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")


def read_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
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

    session_secret: str
    cookie_secure: bool

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def load_settings() -> Settings:
    origins = tuple(
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    )

    max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "20"))

    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        database_url=os.getenv(
            "DATABASE_URL",
            "sqlite:///./data/didim.db",
        ),
        demo_mode=read_bool("DEMO_MODE", True),
        anthropic_api_key=os.getenv(
            "ANTHROPIC_API_KEY",
            "",
        ),
        anthropic_model=os.getenv(
            "ANTHROPIC_MODEL",
            "claude-sonnet-5",
        ),
        frontend_origins=origins,
        upload_dir=resolve_path(
            os.getenv("UPLOAD_DIR", "./data/uploads")
        ),
        max_upload_bytes=max_upload_mb * 1024 * 1024,
        session_secret=os.getenv("SESSION_SECRET", ""),
        cookie_secure=read_bool("COOKIE_SECURE", False),
    )


settings = load_settings()