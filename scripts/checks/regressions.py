"""scripts/regressions.json 의 각 사례를 자동 점검하는 함수들.

규칙: rNNN_* 함수는 (ok: bool, detail: str)을 반환한다.
- status가 fixed인 사례에서 ok=False면 '회귀(FAIL)'
- status가 open인 사례에서 ok=False면 '알려진 문제(KNOWN)', ok=True면 '해결된 듯하니 status 갱신 필요'
앱을 import하는 함수가 있어 worker 프로세스(격리 환경)에서 실행한다.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import frontend_static
from .core import BACKEND, FAIL, FRONTEND, PASS, ROOT, SKIP, Result

REGISTRY = ROOT / "scripts" / "regressions.json"


def _read(path: Path) -> str:
    return path.read_text("utf-8", errors="replace") if path.exists() else ""


# ------------------------------------------------------------------ 공용 점검 로직
def env_example_missing() -> list[str]:
    """config.py가 읽는 환경변수 중 .env.example에 문서화되지 않은 것."""
    names: set[str] = set()
    for path in (BACKEND / "app").rglob("*.py"):
        names |= set(re.findall(r"(?:getenv|env_str|read_bool|environ\.get)\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']", _read(path)))
    documented = set(re.findall(r"^\s*#?\s*([A-Za-z][A-Za-z0-9_]*)\s*=", _read(ROOT / ".env.example"), flags=re.M))
    return sorted(names - documented)


# ------------------------------------------------------------------ 사례별 점검
def r001_risk_prompt_builds():
    from app import risk

    blocks = risk.build_system_blocks()
    return bool(blocks), "시스템 프롬프트를 파일 오류 없이 구성"


def r002_case_delete_with_fk():
    import uuid

    from fastapi.testclient import TestClient
    from sqlalchemy import event
    from sqlmodel import Session

    from app.database import engine
    from app.main import app
    from app.models import Assessment, Attachment, Case, Message, User
    from app.routers.auth import get_current_user

    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _fk_on(conn, _):  # noqa: ANN001
            conn.execute("PRAGMA foreign_keys=ON")

    with TestClient(app) as client:
        with Session(engine) as s:
            user = User(username=f"r002_{uuid.uuid4().hex[:6]}", password_hash="x", name="r002")
            s.add(user)
            s.commit()
            s.refresh(user)
            case = Case(owner_id=user.id)
            s.add(case)
            s.commit()
            s.refresh(case)
            msg = Message(case_id=case.id, role="assistant", content="a")
            s.add(msg)
            s.commit()
            s.refresh(msg)
            s.add(Assessment(case_id=case.id, message_id=msg.id))
            s.add(Attachment(case_id=case.id, filename="a", stored_name="a"))
            s.commit()
            uid, cid = user.id, case.id

        app.dependency_overrides[get_current_user] = lambda: User(id=uid, username="x", password_hash="x", name="x")
        try:
            code = client.delete(f"/api/cases/{cid}").status_code
        finally:
            app.dependency_overrides.clear()
    return code == 204, f"DELETE -> {code} (외래키 강제 상태)"


def r003_citations_migration_exists():
    from app.models import Assessment

    in_migration = any("citations" in _read(p) for p in (BACKEND / "migrations" / "versions").glob("*.py"))
    in_model = "citations" in Assessment.model_fields
    return in_migration and in_model, f"모델={in_model}, 마이그레이션={in_migration}"


def r004_start_scripts_restore_legal_db():
    missing = [
        n for n in ("start.sh", "start.bat", "start.ps1")
        if "app.legal.ingest --from-json" not in _read(ROOT / n)
    ]
    has_json = (ROOT / "data" / "legal" / "articles.json").exists()
    ok = not missing and has_json
    return ok, f"복원 단계 누락: {missing or '없음'}, articles.json: {'있음' if has_json else '없음'}"


def r005_no_oc_key_in_saved_responses():
    pattern = re.compile(r"OC=(?!REDACTED)[0-9A-Za-z]{16,}")
    roots = [ROOT / "data" / "legal", BACKEND / "tests" / "fixtures"]
    bad = [
        str(p.relative_to(ROOT))
        for root in roots for p in root.rglob("*.json") if pattern.search(_read(p))
    ]
    return not bad, f"키 패턴 발견: {bad}" if bad else "저장된 응답에 OC 패턴 없음"


def r006_all_used_classes_have_css():
    missing = frontend_static.undefined_classes()
    detail = "; ".join(f"{c}({','.join(f)})" for c, f in missing.items())
    return not missing, f"CSS 규칙이 없는 클래스: {detail}" if missing else "모든 className에 CSS 규칙 있음"


def r007_no_dead_state():
    problems = frontend_static.dead_state()
    return not problems, "; ".join(problems) if problems else "쓰이지 않는 state 없음"


def r008_spa_served():
    from fastapi.testclient import TestClient

    from app.main import app

    dist = FRONTEND / "dist"
    if not (dist / "index.html").exists():
        return False, "frontend/dist/index.html 없음(빌드 필요)"
    asset = next(iter(sorted((dist / "assets").glob("*.js"))), None)
    with TestClient(app) as c:
        root = c.get("/")
        page = c.get("/register")
        asset_status = c.get(f"/assets/{asset.name}").status_code if asset else 0
        api = c.get("/api/health").headers.get("content-type", "")
    html = "text/html" in root.headers.get("content-type", "")
    ok = root.status_code == 200 and html and page.status_code == 200 and asset_status == 200 and "json" in api
    return ok, f"/={root.status_code}, /register={page.status_code}, /assets/*.js={asset_status}"


def r009_min_length_consistent():
    schema = _read(BACKEND / "app" / "schemas" / "cases.py")
    m = re.search(r"class ChatInput.*?min_length=(\d+)", schema, flags=re.S)
    backend_min = int(m.group(1)) if m else None
    front_min = frontend_static.send_min_length()
    return backend_min == front_min, f"백엔드 min_length={backend_min}, 프런트 전송 조건 <{front_min}"


def r010_regenerate_endpoint_exists():
    """실제 동작으로 점검: 재생성해도 사용자 메시지가 늘지 않고 같은 답변에 버전이 쌓인다."""
    import uuid

    from fastapi.testclient import TestClient
    from sqlmodel import Session, select

    from app.database import engine
    from app.main import app
    from app.models import Case, Message, User
    from app.routers.auth import get_current_user

    with TestClient(app) as client:
        with Session(engine) as s:
            user = User(username=f"r010_{uuid.uuid4().hex[:6]}", password_hash="x", name="r010")
            s.add(user)
            s.commit()
            s.refresh(user)
            case = Case(owner_id=user.id)
            s.add(case)
            s.commit()
            s.refresh(case)
            uid, cid = user.id, case.id

        app.dependency_overrides[get_current_user] = lambda: User(id=uid, username="x", password_hash="x", name="x")
        try:
            client.post(f"/api/cases/{cid}/chat", json={"content": "학부모가 반복해서 욕설을 합니다."})
            with Session(engine) as s:
                before = list(s.exec(select(Message).where(Message.case_id == cid).order_by(Message.id)))
            answer = before[-1]
            resp = client.post(f"/api/cases/{cid}/messages/{answer.id}/regenerate")
            with Session(engine) as s:
                after = list(s.exec(select(Message).where(Message.case_id == cid).order_by(Message.id)))
        finally:
            app.dependency_overrides.clear()

    same_count = len(after) == len(before)
    versions = len(json.loads(after[-1].versions or "[]"))
    ok = resp.status_code == 200 and same_count and versions == 2
    return ok, f"status={resp.status_code}, 메시지 {len(before)}->{len(after)}, 버전 {versions}"


def r011_dist_has_no_stale_assets():
    dist = FRONTEND / "dist"
    index = _read(dist / "index.html")
    if not index:
        return True, "dist 없음"
    referenced = set(re.findall(r"/assets/([^\"'\s>]+)", index))
    present = {p.name for p in (dist / "assets").glob("*")} if (dist / "assets").exists() else set()
    stale = sorted(present - referenced)
    return not stale, f"참조되지 않는 번들 {len(stale)}개: {stale[:4]}" if stale else "오래된 번들 없음"


def r012_retriever_supports_postgres():
    """법령 DB는 SQLite 파일로 유지하고, articles.json만 배포하면 서버가 스스로 만든다."""
    import tempfile

    from sqlalchemy import create_engine

    from app.legal.bootstrap import ensure_legal_db

    # import 줄이 아니라 실제 호출이 있어야 한다
    wired = "ensure_legal_db()" in _read(BACKEND / "app" / "main.py")
    with tempfile.TemporaryDirectory() as tmp:
        state = ensure_legal_db(create_engine(f"sqlite:///{Path(tmp) / 'legal.db'}"))
    ok = wired and state["status"] == "rebuilt" and state["articles"] > 0
    return ok, f"startup 연결={wired}, 빈 폴더에서 {state['status']} (조문 {state['articles']}건)"


def r013_env_example_complete():
    missing = env_example_missing()
    return not missing, f".env.example에 없는 키: {missing}" if missing else "config.py의 모든 키가 문서화됨"


def r014_external_call_guard_targets_exist():
    from app.services import chat_service

    has = hasattr(chat_service, "Anthropic") and hasattr(chat_service, "find_citations")
    patched = "chat_service" in _read(BACKEND / "tests" / "test_api.py")
    return has and patched, f"chat_service 심볼={has}, 테스트가 chat_service 패치={patched}"


def r015_no_inline_styles():
    n = frontend_static.inline_style_count()
    return n == 0, f"인라인 style {n}곳 (데이터 기반 너비 제외)" if n else "인라인 style 없음(데이터 기반 게이지 너비 제외)"


def r017_registration_documents_get_deleted():
    """5년 보관 정책: 기한 계산(신청·심사 시점), 만료 문서 삭제 작업, 기존 데이터 재계산 마이그레이션."""
    from app.services import retention

    parts = {
        "정책 5년": retention.RETENTION_YEARS == 5,
        "신청 시 기한 설정": "retention_deadline" in _read(BACKEND / "app" / "routers" / "registration.py"),
        "심사 시 기한 재계산": _read(BACKEND / "app" / "routers" / "admin_registration.py").count("deadline_iso_from(reviewed_at)") == 2,
        "삭제 작업(CLI)": (BACKEND / "scripts" / "purge_registration_documents.py").exists(),
        "삭제 시 deleted_at 기록": "deleted_at = now_iso()" in _read(BACKEND / "app" / "services" / "retention.py"),
        "기존 데이터 재계산 마이그레이션": any(
            "recompute document_delete_after" in _read(p) for p in (BACKEND / "migrations" / "versions").glob("*.py")
        ),
    }
    bad = [k for k, v in parts.items() if not v]
    return not bad, f"누락: {bad}" if bad else "정책·삭제 작업·마이그레이션 모두 있음"


def r018_login_rate_limited():
    """기본 설정에서 제한이 켜져 있는가(꺼져 있으면 KNOWN). 기능 코드의 정상 동작은 e2e/browser 단계가 켠 상태로 따로 검증한다."""
    # 점검 환경은 기능 검증을 위해 스위치를 켜 두므로, 환경이 아니라 코드의 기본값을 본다
    m = re.search(r'"LOGIN_RATE_LIMIT_ENABLED",\s*(True|False)', _read(BACKEND / "app" / "config.py"))
    if not m or m.group(1) == "False":
        return False, "기본값이 꺼져 있음(데모용)"
    import uuid

    from fastapi.testclient import TestClient
    from sqlmodel import Session

    from app.database import engine
    from app.main import app
    from app.models import User
    from app.security.password import hash_password
    from app.services import login_guard

    name, pw = f"r018_{uuid.uuid4().hex[:6]}", "right-password-1234"
    with Session(engine) as s:
        s.add(User(username=name, password_hash=hash_password(pw), name="r018"))
        s.commit()

    with TestClient(app) as c:
        codes = [
            c.post("/api/auth/login", json={"username": name, "password": "wrong-password"}).status_code
            for _ in range(login_guard.MAX_FAILURES_PER_USER)
        ]
        locked = c.post("/api/auth/login", json={"username": name, "password": pw})
    ok = codes[:-1] == [401] * (len(codes) - 1) and codes[-1] == 429 and locked.status_code == 429
    return ok, f"실패 응답 {codes}, 잠금 중 올바른 비밀번호 -> {locked.status_code}"


def r019_login_limit_consistent():
    """브라우저가 미리 적용하는 한도가 서버 한도와 같은지."""
    text = _read(BACKEND / "app" / "services" / "login_guard.py")
    mf = re.search(r"MAX_FAILURES_PER_USER\s*=\s*(\d+)", text)
    wm = re.search(r"WINDOW_MINUTES\s*=\s*(\d+)", text)
    server = (int(mf.group(1)) if mf else None, int(wm.group(1)) if wm else None)
    client = frontend_static.login_guard_limits()
    return server == client, f"서버(횟수, 분)={server}, 브라우저={client}"


def r020_fresh_database_gets_schema():
    """빈 Postgres에서 서버가 시작될 때 스키마가 만들어지고, 이미 있는 DB는 건드리지 않는다. (Postgres 필요)"""
    url = os.environ.get("CHECK_PG_FRESH_URL")
    if not url:
        return None, "Postgres가 없어 건너뜀 (임시 Postgres가 있을 때만 점검)"

    from alembic import command
    from sqlalchemy import create_engine

    from app import db_migrate

    engine = create_engine(url)
    first = db_migrate.ensure_schema(engine)
    again = db_migrate.ensure_schema(engine)

    command.downgrade(db_migrate.alembic_config(engine), "-1")  # 뒤처진 DB를 만든다
    behind = db_migrate.ensure_schema(engine)
    still_behind = db_migrate.schema_state(engine)["status"]

    ok = (
        first["status"] == "ready" and first.get("migrated") is True
        and again["status"] == "ready" and not again.get("migrated")
        and behind["status"] == "outdated" and still_behind == "outdated"  # 자동으로 올리지 않는다
    )
    return ok, f"빈 DB -> {first['status']}(자동 생성), 재시작 -> {again['status']}, 뒤처진 DB -> {behind['status']}(그대로 둠)"


def r021_empty_env_values_use_defaults():
    """.env.example을 복사한 직후처럼 값이 빈 설정이 기본값을 가리지 않는다."""
    from app.config import load_settings

    keys = ["DATABASE_URL", "MAX_UPLOAD_MB", "REGISTRATION_MAX_UPLOAD_MB", "FRONTEND_ORIGINS", "ANTHROPIC_MODEL",
            "UPLOAD_DIR", "SUPABASE_STORAGE_BUCKET", "DEMO_MODE", "LEGAL_CITATIONS_ENABLED"]
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            os.environ.pop(k, None)
        baseline = load_settings()
        for k in keys:
            os.environ[k] = ""
        blank = load_settings()
    except Exception as exc:
        return False, f"빈 값으로 설정을 읽는 중 예외: {type(exc).__name__}: {exc}"
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return blank == baseline, "빈 값 = 기본값" if blank == baseline else "빈 값이 기본값을 가림"


def r022_mobile_aside_closed_by_default():
    """폰 레이아웃 중단점(상수)이 CSS와 같고, 결과 패널의 초기 상태가 그 값을 쓰는가. 실제 동작은 browser 단계가 본다."""
    const, css = frontend_static.mobile_breakpoints()
    uses = "window.innerWidth > MOBILE_MAX_WIDTH" in _read(FRONTEND / "src" / "workspace" / "Workspace.tsx")
    ok = const is not None and const in css and uses
    return ok, f"MOBILE_MAX_WIDTH={const}, CSS 중단점={sorted(css)}, 초기 상태에서 사용={uses}"


def r016_outdated_db_fails_clearly_and_recovers():
    """뒤처진 DB: 상태는 실시간으로 outdated, 없는 테이블 조회는 503(db_outdated), 마이그레이션 후 재시작 없이 ready. (Postgres 필요)"""
    url = os.environ.get("CHECK_PG_OUTDATED_URL")
    if not url:
        return None, "Postgres가 없어 건너뜀 (임시 Postgres가 있을 때만 점검)"

    from alembic import command
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import DBAPIError

    from app import db_errors, db_migrate

    engine = create_engine(url)
    cfg = db_migrate.alembic_config(engine)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "c4d5e6f7a8b9")  # login_attempts 테이블이 없는 DB

    behind = db_migrate.live_state(engine)["status"]
    response = None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT * FROM login_attempts"))
    except DBAPIError as exc:
        response = db_errors.outdated_db_response(exc, engine)

    command.upgrade(cfg, "head")
    after = db_migrate.live_state(engine)["status"]

    ok = behind == "outdated" and response is not None and response.status_code == 503 and after == "ready"
    return ok, f"뒤처진 DB -> {behind}, 없는 테이블 조회 -> {getattr(response, 'status_code', None)}, 적용 후 -> {after}"


# ------------------------------------------------------------------ 실행
def run_all() -> list[Result]:
    cases = json.loads(REGISTRY.read_text("utf-8"))["cases"]
    results: list[Result] = []
    for case in cases:
        func = globals().get(case.get("check") or "")
        if func is None:
            results.append(Result(case["id"], "SKIP", "자동 점검 없음(수동 확인)"))
            continue
        try:
            ok, detail = func()
        except Exception as exc:  # 점검 자체의 오류는 해당 사례의 실패로 기록
            ok, detail = False, f"점검 중 예외: {type(exc).__name__}: {exc}"
        status = SKIP if ok is None else (PASS if ok else FAIL)  # None = 이 환경에서는 점검할 수 없음
        results.append(Result(case["id"], status, detail))
    return results
