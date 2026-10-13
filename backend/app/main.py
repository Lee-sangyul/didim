from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import engine, init_sqlite_schema  # noqa: F401  (engine: 테스트가 사용)
from .routers import auth_router
from .routers.admin_registration import (
    router as admin_registration_router,
)
from .routers.attachments import (  # noqa: F401  (UPLOAD_DIR: 테스트가 사용)
    UPLOAD_DIR,
    router as attachments_router,
)
from .routers.cases import router as cases_router
from .routers.chat import router as chat_router
from .routers.registration import router as registration_router
from .spa import mount_frontend

app = FastAPI(title="디딤 API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.frontend_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(registration_router)
app.include_router(admin_registration_router)
app.include_router(cases_router)
app.include_router(attachments_router)
app.include_router(chat_router)


@app.on_event("startup")
def startup() -> None:
    if settings.is_sqlite:
        init_sqlite_schema()

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


@app.get("/api/health")
def health() -> dict:
    demo = settings.demo_mode or not settings.anthropic_api_key

    return {
        "ok": True,
        "mode": "demo" if demo else "claude",
        "environment": settings.app_env,
    }


# 모든 API 라우터 뒤에 등록해야 한다 (catch-all 라우트 포함)
mount_frontend(app)
