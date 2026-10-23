#!/usr/bin/env python3
"""디딤 릴리스 점검 스크립트 (단일 진입점).

    python scripts/check.py                  # 전체 점검
    python scripts/check.py --list           # 단계 목록
    python scripts/check.py --only unit e2e  # 일부 단계만
    python scripts/check.py --skip server    # 일부 단계 제외
    python scripts/check.py -v               # 성공 항목의 상세도 출력

브라우저 E2E(`browser` 단계)는 Playwright가 필요하다: pip install -r backend/requirements-dev.txt
(브라우저는 PC에 설치된 Chrome/Edge를 쓴다. 없으면 이 단계만 WARN으로 건너뛴다.)

원칙
- 외부 호출 없음: Claude, 법제처 API, Supabase를 호출하지 않는다 (키를 빈 값으로 덮어쓴 격리 환경).
- 개발 데이터 보호: 모든 DB·업로드·법령 DB는 임시 폴더에서만 만들고 끝나면 지운다.
- Postgres가 설치돼 있으면 임시 클러스터를 띄워 실제 마이그레이션과 외래키를 검증하고,
  없으면 SQLite(외래키 강제)로 대체하며 그 사실을 WARN으로 표시한다.
- 알려진 결함은 scripts/regressions.json 에 기록한다. fixed 사례가 다시 깨지면 FAIL,
  open 사례가 여전히 남아 있으면 KNOWN, 그중 severity=blocker는 릴리스 불가 사유다.

종료 코드: 0 = 릴리스 가능, 1 = FAIL 또는 미해결 blocker 있음, 2 = 점검 스크립트 자체 오류
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.checks import frontend_static  # noqa: E402,F401
from scripts.checks.core import (  # noqa: E402
    BACKEND, FAIL, FRONTEND, KNOWN, PASS, SKIP, WARN, Result, TempPostgres,
    free_port, isolated_env, python_exe, run, run_worker, tail, wait_http,
)

STAGES = [
    ("env", "환경"),
    ("legal", "법령 데이터 복원·검색"),
    ("unit", "백엔드 단위 테스트(pytest)"),
    ("migrate", "DB 마이그레이션"),
    ("e2e", "API 시나리오(E2E)"),
    ("server", "서버 프로세스 기동 스모크"),
    ("frontend", "프런트 타입 검사·빌드"),
    ("browser", "브라우저 E2E(Playwright)"),
    ("release", "릴리스 점검(보안·설정·배포물)"),
    ("regress", "회귀 사례(regressions.json)"),
]


class Ctx:
    def __init__(self, tmp: Path) -> None:
        self.tmp = tmp
        self.pg: TempPostgres | None = None
        self.pg_error: str | None = None
        self.legal_ready = False

    def env(self, **extra: str) -> dict[str, str]:
        return isolated_env(self.tmp, **extra)

    def postgres(self) -> TempPostgres | None:
        """임시 Postgres를 필요할 때 한 번만 띄운다. 불가하면 None."""
        if self.pg is not None or self.pg_error is not None:
            return self.pg
        if not TempPostgres.available():
            self.pg_error = "Postgres(initdb/pg_ctl)가 설치돼 있지 않음"
            return None
        pg = TempPostgres(self.tmp)
        try:
            pg.start()
        except Exception as exc:  # 시작 실패는 환경 문제로 보고하고 계속한다
            self.pg_error = f"임시 Postgres 기동 실패: {str(exc)[:300]}"
            return None
        self.pg = pg
        return pg


def _count(out: str, pattern: str) -> int:
    m = re.search(pattern, out)
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------- 단계 구현
def stage_env(ctx: Ctx) -> list[Result]:
    r: list[Result] = []
    py = python_exe()
    r.append(Result("파이썬 실행 파일", PASS if ".venv" in py else WARN, py if ".venv" in py else f"{py} (저장소 .venv 없음)"))

    code, out = run(
        [py, "-c", "import fastapi,sqlmodel,anthropic,alembic,psycopg,httpx,pytest;print('ok')"], ROOT, ctx.env()
    )
    r.append(Result("백엔드 의존성 import", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 4)))

    npx = shutil.which("npx")
    r.append(Result("Node(npx)", PASS if npx else FAIL, npx or "node/npm이 설치돼 있지 않음"))
    nm = (FRONTEND / "node_modules").exists()
    r.append(Result("frontend/node_modules", PASS if nm else FAIL, "" if nm else "cd frontend && npm install 필요"))

    has_pg = TempPostgres.available()
    r.append(
        Result(
            "Postgres 바이너리(임시 검증용)", PASS if has_pg else WARN,
            "" if has_pg else "없음: 마이그레이션·외래키를 실제 Postgres로 검증하지 못하고 SQLite로 대체됨",
        )
    )
    pw_ok = run([py, "-c", "import playwright"], ROOT, ctx.env())[0] == 0
    r.append(Result("Playwright(브라우저 E2E)", PASS if pw_ok else WARN, "" if pw_ok else "없음: pip install -r backend/requirements-dev.txt (브라우저 E2E 건너뜀)"))
    env_file = (ROOT / ".env").exists()
    r.append(Result(".env 존재", PASS if env_file else WARN, "" if env_file else ".env.example을 복사해 설정 필요"))
    return r


def stage_legal(ctx: Ctx) -> list[Result]:
    r: list[Result] = []
    src = ROOT / "data" / "legal" / "articles.json"
    if not src.exists():
        return [Result("articles.json", FAIL, "data/legal/articles.json 없음 — python -m app.legal.ingest 로 수집 필요")]

    legal_dir = ctx.tmp / "legal"
    legal_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, legal_dir / "articles.json")

    env = ctx.env()
    code, out = run([python_exe(), "-m", "app.legal.ingest", "--from-json"], BACKEND, env)
    if code != 0:
        return [Result("articles.json -> legal.db 복원", FAIL, tail(out))]

    data = json.loads(src.read_text("utf-8"))["laws"]
    db = sqlite3.connect(legal_dir / "legal.db")
    laws = db.execute("select count(*) from law").fetchone()[0]
    arts = db.execute("select count(*) from article").fetchone()[0]
    fts = db.execute("select count(*) from article_fts").fetchone()[0]
    db.close()
    expect_arts = sum(len(x["articles"]) for x in data)
    ok = laws == len(data) and arts == expect_arts and fts == arts and arts > 0
    r.append(Result("articles.json -> legal.db 복원", PASS if ok else FAIL, f"법령 {laws}/{len(data)}, 조문 {arts}/{expect_arts}, FTS {fts}"))

    # TARGET_LAWS(수집 대상)가 articles.json에 모두 반영됐는지 (설정만 바꾸고 재수집을 잊은 경우)
    tree = ast.parse((BACKEND / "app" / "legal" / "config.py").read_text("utf-8"))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "TARGET_LAWS":
            targets = ast.literal_eval(node.value)
    names = {x["name"] for x in data}
    missing = [t for t in targets if t not in names]
    r.append(Result("수집 대상 법령이 모두 articles.json에 있음", PASS if not missing else FAIL, f"누락: {missing}" if missing else f"{len(targets)}개"))

    # 검색 스모크: 조 제목에 검색어가 있는 조문이 후보에 오르는지 (법률 판단이 아닌 어휘 일치 검사)
    snippet = (
        "import json;from app.legal import retriever;"
        "a=retriever.search(['교육활동 침해행위'],8);"
        "print(json.dumps([x.title or '' for x in a],ensure_ascii=False))"
    )
    code, out = run([python_exe(), "-c", snippet], BACKEND, env)
    try:
        titles = json.loads(out.strip().splitlines()[-1])
    except Exception:
        titles = []
    ok = code == 0 and any("교육활동 침해행위" in t for t in titles)
    r.append(Result("검색 스모크('교육활동 침해행위')", PASS if ok else FAIL, f"상위 제목: {titles[:3]}" if not ok else f"{len(titles)}건"))
    ctx.legal_ready = ok or laws > 0
    return r


def stage_unit(ctx: Ctx) -> list[Result]:
    # backend/tests 전체: 단위 테스트 + API 회귀 테스트(test_api.py). 환경은 tests/conftest.py가 격리한다.
    code, out = run([python_exe(), "-m", "pytest", "-q", "-p", "no:cacheprovider"], BACKEND, ctx.env(), timeout=600)
    passed, failed = _count(out, r"(\d+) passed"), _count(out, r"(\d+) failed")
    err = _count(out, r"(\d+) error")
    ok = code == 0
    return [Result("pytest backend", PASS if ok else FAIL, f"통과 {passed}, 실패 {failed}, 오류 {err}" + ("" if ok else "\n" + tail(out, 25)))]


def _alembic(env: dict[str, str], *args: str) -> tuple[int, str]:
    return run([python_exe(), "-m", "alembic", "-c", str(BACKEND / "alembic.ini"), *args], BACKEND, env, timeout=180)


def stage_migrate(ctx: Ctx) -> list[Result]:
    r: list[Result] = []
    code, out = _alembic(ctx.env(), "heads")
    heads = [ln for ln in out.splitlines() if "(head)" in ln]
    r.append(Result("마이그레이션 head가 하나", PASS if code == 0 and len(heads) == 1 else FAIL, f"head {len(heads)}개\n{tail(out, 4)}" if len(heads) != 1 else heads[0].strip()))

    pg = ctx.postgres()
    if pg is None:
        # Postgres가 없으면 DB 없이 PG용 SQL 생성만 확인 (실행은 못 함)
        env = ctx.env(DATABASE_URL="postgresql+psycopg://u:p@localhost:5432/db")
        code, out = _alembic(env, "upgrade", "head", "--sql")
        ok = code == 0 and "CREATE TABLE" in out
        r.append(Result("마이그레이션 SQL 생성(Postgres 방언, 오프라인)", PASS if ok else FAIL, tail(out, 6) if not ok else ""))
        r.append(Result("마이그레이션 실제 적용·모델 일치·되돌리기", WARN, f"실행하지 못함: {ctx.pg_error}"))
        return r

    url = pg.create_db("mig")
    env = ctx.env(DATABASE_URL=url)
    code, out = _alembic(env, "upgrade", "head")
    r.append(Result("빈 Postgres에 upgrade head", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 10)))
    if code != 0:
        return r

    r.extend(run_worker("drift", env))

    code, out = _alembic(env, "downgrade", "base")
    r.append(Result("downgrade base", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 8)))
    code, out = _alembic(env, "upgrade", "head")
    r.append(Result("다운그레이드 후 다시 upgrade head", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 8)))
    return r


def stage_e2e(ctx: Ctx) -> list[Result]:
    r: list[Result] = []
    r.extend(run_worker("e2e", ctx.env(DATABASE_URL=f"sqlite:///{(ctx.tmp / 'e2e_sqlite.db').as_posix()}"), "SQLite+FK"))

    pg = ctx.postgres()
    if pg is None:
        r.append(Result("[Postgres] API 시나리오", WARN, f"실행하지 못함: {ctx.pg_error}"))
        return r
    url = pg.create_db("e2e")
    env = ctx.env(DATABASE_URL=url)
    code, out = _alembic(env, "upgrade", "head")
    if code != 0:
        r.append(Result("[Postgres] 시나리오용 스키마(upgrade head)", FAIL, tail(out, 8)))
        return r
    r.extend(run_worker("e2e", env, "Postgres"))
    return r


def _http(opener, method: str, url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


@contextlib.contextmanager
def _server(ctx: Ctx, env: dict[str, str], name: str):
    """실제 uvicorn 프로세스를 띄우고 (base_url | None, 로그 경로)를 준다. 끝나면 반드시 종료한다."""
    port = free_port()
    log_path = ctx.tmp / f"{name}.log"
    log = log_path.open("w")
    proc = subprocess.Popen(
        [python_exe(), "-m", "uvicorn", "app.main:app", "--app-dir", str(BACKEND),
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        yield (base if wait_http(f"{base}/api/health", 25) else None), log_path
    finally:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def _seed_user(env: dict[str, str], username: str, password: str) -> tuple[int, str]:
    """서버가 만든 스키마에 점검용 계정을 직접 넣는다 (가입 승인 흐름은 backend/tests의 pytest가 담당)."""
    seed = (
        "import sys;from sqlmodel import Session;from app.database import engine;"
        "from app.models import User;from app.security.password import hash_password;"
        "s=Session(engine);s.add(User(username=sys.argv[1],password_hash=hash_password(sys.argv[2]),name='점검'));s.commit()"
    )
    return run([python_exe(), "-c", seed, username, password], BACKEND, env)


def stage_server(ctx: Ctx) -> list[Result]:
    r: list[Result] = []
    env = ctx.env(DATABASE_URL=f"sqlite:///{(ctx.tmp / 'server.db').as_posix()}")

    with _server(ctx, env, "server") as (base, log_path):
        r.append(Result("서버 프로세스 기동(/api/health)", PASS if base else FAIL, "" if base else "25초 안에 응답 없음\n" + tail(log_path.read_text(errors="replace"), 10)))
        if not base:
            return r

        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        if (FRONTEND / "dist" / "index.html").exists():
            code, body = _http(opener, "GET", f"{base}/")
            r.append(Result("실서버가 프런트 화면(/)을 서빙", PASS if code == 200 and 'id="root"' in body else FAIL, f"{code}"))
        code, body = _http(opener, "GET", f"{base}/api/cases")
        r.append(Result("미로그인 /api/cases -> 401", PASS if code == 401 else FAIL, f"{code}"))

        code, out = _seed_user(env, "srv_check", "check-only-pw-1234")
        if code != 0:
            r.append(Result("점검용 계정 생성", FAIL, tail(out, 6)))
            return r

        code, body = _http(opener, "POST", f"{base}/api/auth/login", {"username": "srv_check", "password": "check-only-pw-1234"})
        r.append(Result("실서버 로그인", PASS if code == 200 else FAIL, f"{code} {body[:100]}"))
        if code != 200:
            return r
        code, body = _http(opener, "POST", f"{base}/api/cases", {"title": "서버 점검"})
        case_id = json.loads(body).get("id") if code == 200 else None
        r.append(Result("실서버 상담 생성", PASS if case_id else FAIL, f"{code}"))
        if case_id:
            code, body = _http(opener, "POST", f"{base}/api/cases/{case_id}/chat", {"content": "학부모가 반복해서 욕설을 합니다."})
            kinds = [json.loads(b[6:])["type"] for b in body.split("\n\n") if b.startswith("data: ")]
            r.append(Result("실서버 채팅 스트리밍", PASS if code == 200 and "done" in kinds and "error" not in kinds else FAIL, f"{code} {kinds[:3]}..."))

    # 처음 받은 PC처럼 **빈 Postgres**에 서버만 띄워도 스키마가 만들어지고 요청이 500이 아니어야 한다 (R020)
    pg = ctx.postgres()
    if pg is None:
        r.append(Result("빈 Postgres 첫 기동(스키마 자동 준비)", WARN, f"실행하지 못함: {ctx.pg_error}"))
        return r

    pg_env = ctx.env(DATABASE_URL=pg.create_db("firstboot"))
    with _server(ctx, pg_env, "firstboot") as (base, log_path):
        if not base:
            r.append(Result("빈 Postgres 첫 기동(스키마 자동 준비)", FAIL, tail(log_path.read_text(errors="replace"), 12)))
            return r
        opener = urllib.request.build_opener()
        code, body = _http(opener, "GET", f"{base}/api/health/db")
        state = json.loads(body) if code == 200 else {}
        r.append(Result(
            "빈 Postgres 첫 기동 시 스키마 자동 생성(/api/health/db)",
            PASS if state.get("status") == "ready" and state.get("migrated") else FAIL, f"{code} {state}",
        ))
        code, _ = _http(opener, "POST", f"{base}/api/auth/login", {"username": "nobody", "password": "wrong-password"})
        r.append(Result("빈 Postgres 첫 기동 직후 로그인 요청이 500이 아님(401)", PASS if code == 401 else FAIL, f"{code}"))

        # 서버가 떠 있는 동안 DB가 코드보다 뒤처지는 상황(배포 순서 위반, R016).
        # 정책: 기동은 계속되고, 영향받는 요청만 설명 있는 503으로 실패하며, 마이그레이션 적용 시 재시작 없이 복구된다.
        code, out = _alembic(pg_env, "downgrade", "c4d5e6f7a8b9")
        r.append(Result("DB를 두 단계 되돌려 '코드가 먼저 배포된' 상황을 만듦", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 6)))
        if code == 0:
            code, body = _http(opener, "POST", f"{base}/api/auth/login", {"username": "nobody", "password": "wrong-password"})
            r.append(Result(
                "뒤처진 DB: 로그인 요청이 설명 있는 503(db_outdated)",
                PASS if code == 503 and '"db_outdated"' in body and "마이그레이션" in body else FAIL, f"{code} {body[:100]}",
            ))
            code, body = _http(opener, "GET", f"{base}/api/health/db")
            r.append(Result("뒤처진 DB: /api/health/db가 outdated", PASS if code == 200 and '"outdated"' in body else FAIL, f"{code} {body[:100]}"))
            code, _ = _http(opener, "GET", f"{base}/api/health")
            r.append(Result("뒤처진 DB에서도 서버는 계속 동작(/api/health 200)", PASS if code == 200 else FAIL, f"{code}"))

            code, out = _alembic(pg_env, "upgrade", "head")
            r.append(Result("마이그레이션 적용(서버는 그대로 실행 중)", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 6)))
            code, body = _http(opener, "GET", f"{base}/api/health/db")
            r.append(Result("재시작 없이 /api/health/db가 ready로 복구", PASS if code == 200 and '"ready"' in body else FAIL, f"{code} {body[:100]}"))
            code, _ = _http(opener, "POST", f"{base}/api/auth/login", {"username": "nobody", "password": "wrong-password"})
            r.append(Result("재시작 없이 로그인 요청이 정상 처리(401)", PASS if code == 401 else FAIL, f"{code}"))
    return r


def _build_frontend(ctx: Ctx, dist: Path, **extra_env: str) -> tuple[int, str]:
    npx = shutil.which("npx") or "npx"
    return run([npx, "--no-install", "vite", "build", "--outDir", str(dist), "--emptyOutDir"], FRONTEND, ctx.env(**extra_env), timeout=300)


def stage_frontend(ctx: Ctx) -> list[Result]:
    npx = shutil.which("npx")
    if not npx or not (FRONTEND / "node_modules").exists():
        return [Result("프런트 점검", FAIL, "node/npm 또는 frontend/node_modules 없음 (환경 단계 참고)")]
    env = ctx.env()
    r: list[Result] = []

    # 산출물·tsbuildinfo가 저장소(tracked 파일)를 바꾸지 않도록 임시 위치로 보낸다.
    code, out = run([npx, "--no-install", "tsc", "--noEmit", "--incremental", "false", "-p", "."], FRONTEND, env, timeout=300)
    r.append(Result("tsc 타입 검사", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 15)))

    for title, func in (
        ("CSS 분할 구조(app.css @import 목차)", frontend_static.css_import_problems),
        ("다크 모드 토큰(.dark-mode)", frontend_static.dark_mode_problems),
        ("인쇄 스타일(@page, @media print)", frontend_static.print_problems),
    ):
        problems = func()
        r.append(Result(title, PASS if not problems else FAIL, "; ".join(problems)))

    dist = ctx.tmp / "dist"
    code, out = _build_frontend(ctx, dist)
    r.append(Result("vite build", PASS if code == 0 else FAIL, "" if code == 0 else tail(out, 15)))
    if code == 0:
        # frontend/dist는 git에 두는 산출물이므로 소스와 어긋나면 배포 화면이 옛 버전이 된다
        def refs_of(path: Path) -> set[str]:
            text = path.read_text("utf-8") if path.exists() else ""
            return set(re.findall(r"""(?:src|href)=["']/assets/([^"']+)""", text))

        built, committed = refs_of(dist / "index.html"), refs_of(FRONTEND / "dist" / "index.html")
        fresh = built == committed
        r.append(Result(
            "커밋된 frontend/dist가 현재 소스와 일치", PASS if fresh else WARN,
            "" if fresh else "릴리스 전에 `cd frontend && npm run build` 후 dist를 커밋하세요 (배포 화면이 옛 버전입니다)",
        ))

        index = (dist / "index.html").read_text("utf-8") if (dist / "index.html").exists() else ""
        refs = re.findall(r"""(?:src|href)=["']/(assets/[^"']+)""", index)
        missing = [x for x in refs if not (dist / x).exists()]
        ok = bool(refs) and not missing
        r.append(Result("빌드 산출물(index.html 참조 파일 존재)", PASS if ok else FAIL, f"참조 {len(refs)}개, 누락 {missing}"))
    return r


def stage_browser(ctx: Ctx) -> list[Result]:
    code, _ = run([python_exe(), "-c", "import playwright"], ROOT, ctx.env())
    if code != 0:
        return [Result("Playwright 설치", WARN, "설치되지 않아 브라우저 E2E를 건너뜀: pip install -r backend/requirements-dev.txt")]

    # 로그인 잠금 화면이 켜진 별도 빌드를 쓴다 (배포용 기본 빌드는 꺼져 있다)
    dist = ctx.tmp / "dist-browser"
    code, out = _build_frontend(ctx, dist, VITE_LOGIN_GUARD="true")
    if code != 0:
        return [Result("브라우저 E2E용 프런트 빌드", FAIL, tail(out, 12))]

    env = ctx.env(
        DATABASE_URL=f"sqlite:///{(ctx.tmp / 'browser.db').as_posix()}",
        FRONTEND_DIST=str(dist),
    )
    user, pw = "e2e_check", "check-only-pw-1234"

    with _server(ctx, env, "browser") as (base, log_path):
        if not base:
            return [Result("브라우저 E2E용 서버 기동", FAIL, tail(log_path.read_text(errors="replace"), 10))]
        code, out = _seed_user(env, user, pw)
        if code != 0:
            return [Result("점검용 계정 생성", FAIL, tail(out, 6))]
        return run_worker("browser", env, base, user, pw, timeout=300)


SECRET_PATTERNS = {
    "Anthropic API 키": re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    "JWT/서비스 키": re.compile(r"eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),
    "법제처 OC 키": re.compile(r"OC=(?!REDACTED)[0-9A-Za-z]{20,}"),
    "개인 키": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}


def _env_secret_values() -> dict[str, str]:
    """.env의 비밀 값들 (출력하지 않고 검색에만 쓴다)."""
    values: dict[str, str] = {}
    env_file = ROOT / ".env"
    if not env_file.exists():
        return values
    for line in env_file.read_text("utf-8", errors="replace").splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip().strip("\"'")
        upper = key.upper()
        if len(val) >= 8 and any(t in upper for t in ("KEY", "SECRET", "PW", "PASSWORD", "TOKEN", "OC")):
            values[key] = val
        if upper == "DATABASE_URL":
            pw = re.search(r"://[^:/@]+:([^@]+)@", val)
            if pw and len(pw.group(1)) >= 8 and not pw.group(1).startswith("["):
                values["DATABASE_URL(비밀번호)"] = pw.group(1)
    return values


GENERATED_OK = {"data/legal/legal.db", ".env"}  # 문서에는 나오지만 저장소에는 없는 생성물·로컬 파일


def _check_agents_doc() -> Result:
    """AGENTS.md가 가리키는 경로·결함 ID가 실제로 존재하는지 (낡은 문서는 AI를 오도한다)."""
    doc = ROOT / "AGENTS.md"
    if not doc.exists():
        return Result("AGENTS.md의 경로·결함 ID 유효", FAIL, "AGENTS.md 없음")
    text = doc.read_text("utf-8")

    names = {p.name for p in ROOT.rglob("*") if p.is_file() and not any(
        part in (".git", "node_modules", ".venv", "dist", "__pycache__") for part in p.parts)}
    tokens = set(re.findall(r"`([A-Za-z0-9_./-]+(?:\.(?:py|tsx?|json|css|bat|ps1|sh|md|ini|txt)|/))`", text))
    missing = []
    for tok in sorted(tokens):
        if tok in GENERATED_OK or tok.startswith(("python", "npm")):
            continue
        ok = (ROOT / tok).exists() if "/" in tok.rstrip("/") or tok.endswith("/") else (tok in names or (ROOT / tok).exists())
        if not ok:
            missing.append(tok)

    registry = {c["id"] for c in json.loads((ROOT / "scripts" / "regressions.json").read_text("utf-8"))["cases"]}
    bad_ids = sorted(set(re.findall(r"\bR\d{3}\b", text)) - registry)

    problems = [f"없는 경로: {missing}"] * bool(missing) + [f"레지스트리에 없는 결함 ID: {bad_ids}"] * bool(bad_ids)
    return Result("AGENTS.md의 경로·결함 ID 유효", PASS if not problems else FAIL, "; ".join(problems))


def stage_release(ctx: Ctx) -> list[Result]:
    r: list[Result] = []
    required = [
        ".env.example", "README.md", "backend/requirements.txt", "backend/alembic.ini",
        "frontend/package.json", "frontend/package-lock.json", "data/legal/articles.json",
        "json/program_config.json", "json/input.json", "json/output.json",
        "start.sh", "start.bat", "start.ps1", "scripts/regressions.json",
        "AGENTS.md", "CLAUDE.md",
    ]
    missing = [p for p in required if not (ROOT / p).exists()]
    r.append(Result("필수 파일 존재", PASS if not missing else FAIL, f"누락: {missing}" if missing else f"{len(required)}개"))

    r.append(_check_agents_doc())

    git = shutil.which("git")
    tracked: list[str] = []
    if git and (ROOT / ".git").exists():
        code, out = run([git, "ls-files", "-z"], ROOT, ctx.env())
        tracked = [p for p in out.split("\0") if p] if code == 0 else []

    if not tracked:
        r.append(Result("비밀키 커밋 점검", SKIP, "git 저장소가 아니어서 건너뜀"))
    else:
        bad_files = [p for p in tracked if p in (".env",) or p.endswith(".db") or p.startswith("data/uploads/")]
        r.append(Result("추적 금지 파일(.env, *.db, uploads)", PASS if not bad_files else FAIL, f"추적 중: {bad_files}" if bad_files else ""))

        secrets = _env_secret_values()
        hits: dict[str, set[str]] = {}
        for rel in tracked:
            path = ROOT / rel
            try:
                if not path.is_file() or path.stat().st_size > 5_000_000:
                    continue
                raw = path.read_bytes()
            except OSError:
                continue
            if b"\0" in raw[:2048]:
                continue  # 바이너리
            text = raw.decode("utf-8", errors="replace")
            for label, pat in SECRET_PATTERNS.items():
                if pat.search(text):
                    hits.setdefault(rel, set()).add(label)
            for key, val in secrets.items():
                if val in text:
                    hits.setdefault(rel, set()).add(f".env의 {key} 값")
        detail = "; ".join(f"{p}: {', '.join(sorted(v))}" for p, v in sorted(hits.items()))
        r.append(Result("추적 파일에 비밀키·토큰 없음", PASS if not hits else FAIL, detail if hits else f"{len(tracked)}개 파일 검사"))

        code, out = run([git, "status", "--porcelain"], ROOT, ctx.env())
        dirty = [ln for ln in out.splitlines() if ln.strip()]
        r.append(Result("작업 트리가 깨끗함(커밋된 상태에서 릴리스)", PASS if not dirty else WARN, f"커밋되지 않은 변경 {len(dirty)}개" if dirty else ""))

    # .env.example에 실제 값처럼 보이는 자격 정보가 남아 있는지 (값은 출력하지 않는다)
    example = (ROOT / ".env.example").read_text("utf-8", errors="replace") if (ROOT / ".env.example").exists() else ""
    risky: list[str] = []
    for line in example.splitlines():
        m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(\S.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if re.search(r"(PW|PASSWORD|SECRET|TOKEN|API_KEY)", key, flags=re.I) and val:
            risky.append(key)
        if key.upper() == "DATABASE_URL" and "supabase" in val.lower() and "[" not in val:
            risky.append("DATABASE_URL(실제 호스트·프로젝트 식별자)")
        if key.upper() == "DATABASE_URL" and re.search(r"supabase\.com", val) and re.search(r"postgres\.[a-z0-9]{15,}", val):
            risky.append("DATABASE_URL(프로젝트 식별자)")
    risky = sorted(set(risky))
    r.append(Result(".env.example에 실제 값 형태의 자격 정보 없음", PASS if not risky else WARN, f"확인 필요한 키: {risky}" if risky else ""))

    cfg = (BACKEND / "app" / "config.py").read_text("utf-8")
    m = re.search(r'"LOGIN_RATE_LIMIT_ENABLED",\s*(True|False)', cfg)
    off = not m or m.group(1) == "False"
    r.append(Result(
        "로그인 시도 제한이 기본으로 켜져 있음", WARN if off else PASS,
        "꺼져 있음(데모용, 2026-10). 운영 공개 전에 .env의 LOGIN_RATE_LIMIT_ENABLED=true, 프런트는 VITE_LOGIN_GUARD=true로 빌드 (TODO.md)" if off else "",
    ))

    pkg = json.loads((FRONTEND / "package.json").read_text("utf-8"))
    floating = sorted(k for k, v in {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}.items() if v in ("latest", "*"))
    r.append(Result("프런트 의존성 버전 고정", PASS if not floating else WARN, f"latest 사용: {floating} (package-lock.json이 실제 버전을 고정)" if floating else ""))

    loose = [
        ln.strip() for ln in (BACKEND / "requirements.txt").read_text("utf-8").splitlines()
        if ln.strip() and not ln.startswith("#") and "==" not in ln
    ]
    r.append(Result("백엔드 의존성 버전 고정", PASS if not loose else WARN, f"고정되지 않음: {loose}" if loose else ""))
    return r


def stage_regress(ctx: Ctx) -> list[Result]:
    registry = {c["id"]: c for c in json.loads((ROOT / "scripts" / "regressions.json").read_text("utf-8"))["cases"]}
    extra: dict[str, str] = {}
    pg = ctx.postgres()
    if pg is not None:
        # 점검마다 서로 다른 DB를 쓴다(앞선 점검이 남긴 상태가 다음 점검의 전제를 깨지 않게)
        extra["CHECK_PG_FRESH_URL"] = pg.create_db("regress_fresh")  # R020: 빈 DB에서 시작
        extra["CHECK_PG_OUTDATED_URL"] = pg.create_db("regress_outdated")  # R016: 뒤처진 DB 만들기
    raw = run_worker("regress", ctx.env(**extra))
    out: list[Result] = []
    for item in raw:
        case = registry.get(item.name)
        if case is None:
            out.append(item)  # worker 자체 오류
            continue
        label = f"{case['id']} {case['title']}"
        blocker = case.get("severity") == "blocker"
        if item.status == SKIP:
            detail = item.detail if case.get("check") else "자동 점검 없음 — " + case.get("symptom", "")
            out.append(Result(label, SKIP, detail, blocker=False))
        elif case["status"] == "fixed":
            out.append(Result(label, PASS if item.status == PASS else FAIL, item.detail))
        elif item.status == PASS:  # open인데 통과
            out.append(Result(label, WARN, "해결된 것으로 보임 — regressions.json의 status를 fixed로 바꾸세요. " + item.detail))
        else:
            out.append(Result(label, KNOWN, f"[{case.get('severity')}] {item.detail}", blocker=blocker))
    return out


RUNNERS = {
    "env": stage_env, "legal": stage_legal, "unit": stage_unit,
    "migrate": stage_migrate, "e2e": stage_e2e, "server": stage_server,
    "frontend": stage_frontend, "browser": stage_browser,
    "release": stage_release, "regress": stage_regress,
}

ICON = {PASS: "PASS ", FAIL: "FAIL ", WARN: "WARN ", SKIP: "SKIP ", KNOWN: "KNOWN"}


def main() -> int:
    ap = argparse.ArgumentParser(description="디딤 릴리스 점검", formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="단계 목록 출력")
    ap.add_argument("--only", nargs="+", metavar="STAGE", help="지정한 단계만 실행")
    ap.add_argument("--skip", nargs="+", metavar="STAGE", default=[], help="지정한 단계 제외")
    ap.add_argument("--keep-tmp", action="store_true", help="임시 폴더를 지우지 않음(디버깅용)")
    ap.add_argument("-v", "--verbose", action="store_true", help="통과 항목의 상세도 출력")
    args = ap.parse_args()

    names = [n for n, _ in STAGES]
    if args.list:
        for n, title in STAGES:
            print(f"{n:<10} {title}")
        return 0
    chosen = args.only or names
    unknown = [n for n in [*chosen, *args.skip] if n not in names]
    if unknown:
        print(f"알 수 없는 단계: {unknown}. --list 로 확인하세요.", file=sys.stderr)
        return 2
    chosen = [n for n in chosen if n not in args.skip]
    # unit/regress는 복원된 법령 DB가 필요하므로 legal을 앞에 둔다
    if any(n in chosen for n in ("unit", "regress")) and "legal" not in chosen:
        chosen.insert(0, "legal")

    tmp = Path(tempfile.mkdtemp(prefix="didim-check-"))
    ctx = Ctx(tmp)
    all_results: list[tuple[str, list[Result]]] = []
    started = time.time()
    try:
        for name in [n for n in names if n in chosen]:
            title = dict(STAGES)[name]
            print(f"\n== [{name}] {title}", flush=True)
            t0 = time.time()
            try:
                results = RUNNERS[name](ctx)
            except Exception as exc:  # 한 단계의 스크립트 오류가 전체를 막지 않도록
                results = [Result(f"{name} 단계 실행", FAIL, f"점검 스크립트 오류: {type(exc).__name__}: {exc}")]
            for res in results:
                print(f"  [{ICON[res.status]}] {res.name}")
                show = res.detail and (res.status != PASS or args.verbose)
                if show:
                    for line in res.detail.splitlines():
                        print(f"           {line}")
            all_results.append((name, results))
            print(f"  ({time.time() - t0:.1f}초)", flush=True)
    finally:
        if ctx.pg is not None:
            ctx.pg.stop()
        if args.keep_tmp:
            print(f"\n임시 폴더 유지: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    # ---- 요약
    print("\n" + "=" * 64)
    print(f"{'단계':<10}{'PASS':>6}{'FAIL':>6}{'WARN':>6}{'SKIP':>6}{'KNOWN':>7}")
    totals = {PASS: 0, FAIL: 0, WARN: 0, SKIP: 0, KNOWN: 0}
    for name, results in all_results:
        c = {s: sum(1 for x in results if x.status == s) for s in totals}
        for s in totals:
            totals[s] += c[s]
        print(f"{name:<10}{c[PASS]:>6}{c[FAIL]:>6}{c[WARN]:>6}{c[SKIP]:>6}{c[KNOWN]:>7}")
    print(f"{'합계':<10}{totals[PASS]:>6}{totals[FAIL]:>6}{totals[WARN]:>6}{totals[SKIP]:>6}{totals[KNOWN]:>7}")

    flat = [x for _, rs in all_results for x in rs]
    fails = [x for x in flat if x.status == FAIL]
    blockers = [x for x in flat if x.status == KNOWN and x.blocker]
    if fails:
        print("\n실패 항목")
        for x in fails:
            print(f"  - {x.name}")
    if blockers:
        print("\n릴리스를 막는 미해결 결함(blocker)")
        for x in blockers:
            print(f"  - {x.name}")
    others = [x for x in flat if x.status == KNOWN and not x.blocker]
    if others:
        print("\n알려진 미해결(참고)")
        for x in others:
            print(f"  - {x.name}")

    ready = not fails and not blockers
    print(f"\n판정: {'릴리스 가능' if ready else '릴리스 불가'}  (소요 {time.time() - started:.0f}초)")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
