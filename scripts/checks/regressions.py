"""scripts/regressions.json 의 각 사례를 자동 점검하는 함수들.

규칙: rNNN_* 함수는 (ok: bool, detail: str)을 반환한다.
- status가 fixed인 사례에서 ok=False면 '회귀(FAIL)'
- status가 open인 사례에서 ok=False면 '알려진 문제(KNOWN)', ok=True면 '해결된 듯하니 status 갱신 필요'
앱을 import하는 함수가 있어 worker 프로세스(격리 환경)에서 실행한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import frontend_static
from .core import BACKEND, FAIL, FRONTEND, PASS, ROOT, Result

REGISTRY = ROOT / "scripts" / "regressions.json"


def _read(path: Path) -> str:
    return path.read_text("utf-8", errors="replace") if path.exists() else ""


# ------------------------------------------------------------------ 공용 점검 로직
def env_example_missing() -> list[str]:
    """config.py가 읽는 환경변수 중 .env.example에 문서화되지 않은 것."""
    names: set[str] = set()
    for path in (BACKEND / "app").rglob("*.py"):
        names |= set(re.findall(r"(?:getenv|read_bool|environ\.get)\(\s*[\"']([A-Z][A-Z0-9_]+)[\"']", _read(path)))
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
    found = [p.name for p in (BACKEND / "app" / "routers").glob("*.py") if "regenerate" in _read(p).lower()]
    return bool(found), "전용 재생성 엔드포인트 있음" if found else "재생성 전용 엔드포인트 없음(/chat 재사용)"


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
    text = _read(BACKEND / "app" / "legal" / "retriever.py")
    ok = "tsvector" in text or "pg_trgm" in text
    return ok, "Postgres 검색 경로 있음" if ok else "FTS5(SQLite) 전용 구현"


def r013_env_example_complete():
    missing = env_example_missing()
    return not missing, f".env.example에 없는 키: {missing}" if missing else "config.py의 모든 키가 문서화됨"


def r014_external_call_guard_targets_exist():
    from app.services import chat_service

    has = hasattr(chat_service, "Anthropic") and hasattr(chat_service, "find_citations")
    patched = "chat_service" in _read(ROOT / "test_didim.py")
    return has and patched, f"chat_service 심볼={has}, 테스트가 chat_service 패치={patched}"


def r015_no_inline_styles():
    n = frontend_static.inline_style_count()
    allow = sorted(frontend_static.UNSTYLED_OK)
    return n == 0, f"인라인 style {n}곳, CSS 규칙 없이 허용 중인 클래스: {allow}"


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
        results.append(Result(case["id"], PASS if ok else FAIL, detail))
    return results
