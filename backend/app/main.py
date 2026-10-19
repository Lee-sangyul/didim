from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import DBAPIError

from .config import settings
from .db_errors import outdated_db_response
from .db_migrate import ensure_schema, live_state
from .legal.bootstrap import ensure_legal_db
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


@app.exception_handler(DBAPIError)
async def handle_db_error(request: Request, exc: DBAPIError):
    """DB가 뒤처져서 난 오류만 503으로 바꾼다. 그 밖의 DB 오류는 기존처럼 500으로 둔다."""
    if not settings.is_sqlite:
        response = await run_in_threadpool(outdated_db_response, exc, engine)

        if response is not None:
            return response

    raise exc


@app.on_event("startup")
def startup() -> None:
    if settings.is_sqlite:
        init_sqlite_schema()
        app.state.db = {"status": "sqlite"}
    else:
        # 빈 DB면 처음 한 번 마이그레이션을 적용하고, 뒤처진 DB는 자동으로 바꾸지 않고 경고한다
        app.state.db = ensure_schema(engine)

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 법령 검색 DB를 articles.json에서 준비한다. 실패해도 서버는 뜬다(근거 조문만 빠짐).
    app.state.legal = (
        ensure_legal_db()
        if settings.legal_citations_enabled
        else {"status": "disabled", "laws": 0, "articles": 0}
    )


@app.get("/api/health")
def health() -> dict:
    demo = settings.demo_mode or not settings.anthropic_api_key

    return {
        "ok": True,
        "mode": "demo" if demo else "claude",
        "environment": settings.app_env,
    }


@app.get("/api/health/db")
def health_db() -> dict:
    """DB 스키마 상태: sqlite | ready | outdated | unmanaged | error. (접속 정보는 포함하지 않는다)

    매번 DB에서 다시 읽으므로 마이그레이션을 적용하면 재시작 없이 바로 반영된다.
    """
    if settings.is_sqlite:
        return {"status": "sqlite"}

    state = live_state(engine)

    if getattr(app.state, "db", {}).get("migrated"):
        state["migrated"] = True  # 이 서버가 시작할 때 빈 DB를 처음 만들었다

    return state


@app.get("/api/health/legal")
def health_legal() -> dict:
    """법령 검색 DB 준비 상태(ready | rebuilt | missing_source | error | disabled)와 건수."""
    return getattr(app.state, "legal", None) or {"status": "unknown", "laws": 0, "articles": 0}


# 모든 API 라우터 뒤에 등록해야 한다 (catch-all 라우트 포함)
mount_frontend(app)
