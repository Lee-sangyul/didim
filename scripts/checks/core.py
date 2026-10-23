"""점검 스크립트 공통: 결과 모델, 격리된 환경변수, 하위 프로세스 실행, 임시 Postgres."""
from __future__ import annotations

import atexit
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

PASS, FAIL, WARN, SKIP, KNOWN = "PASS", "FAIL", "WARN", "SKIP", "KNOWN"
RESULT_MARK = "@@RESULT@@"  # worker가 stdout 마지막에 JSON으로 결과를 내보낼 때의 표식


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""
    blocker: bool = False  # KNOWN(알려진 미해결) 중 릴리스를 막는 것

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def python_exe() -> str:
    """백엔드 의존성이 설치된 파이썬. 저장소의 .venv가 있으면 그것을 쓴다."""
    for candidate in (ROOT / ".venv" / "bin" / "python", ROOT / ".venv" / "Scripts" / "python.exe"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def isolated_env(tmp: Path, **extra: str) -> dict[str, str]:
    """외부 호출·실제 데이터를 쓰지 않는 환경.

    키를 빈 문자열로 '설정'해 두는 것이 중요하다: app.config가 .env를 읽어도
    이미 설정된 환경변수는 덮어쓰지 않으므로 실제 API 키가 새어 들어오지 않는다.
    """
    env = os.environ.copy()
    env.update(
        APP_ENV="test",
        DEMO_MODE="true",
        ANTHROPIC_API_KEY="",
        LAW_API_OC="",
        SUPABASE_URL="",
        SUPABASE_SECRET_KEY="",
        COOKIE_SECURE="false",
        LOGIN_RATE_LIMIT_ENABLED="true",  # 기본은 꺼짐(데모용)이지만 기능 자체는 계속 점검한다
        DATABASE_URL=f"sqlite:///{(tmp / 'check.db').as_posix()}",
        UPLOAD_DIR=str(tmp / "uploads"),
        LEGAL_DATA_DIR=str(tmp / "legal"),
        PYTHONPATH=str(BACKEND),
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
    )
    env.update(extra)
    return env


def run(cmd: list[str], cwd: Path, env: dict[str, str], timeout: int = 300) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return 124, f"시간 초과({timeout}초): {' '.join(cmd)}\n{e.stdout or ''}"
    except FileNotFoundError as e:
        return 127, f"실행 파일을 찾을 수 없음: {e}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def tail(text: str, lines: int = 12) -> str:
    return "\n".join(text.strip().splitlines()[-lines:])


def parse_worker_results(output: str) -> list[Result] | None:
    for line in reversed(output.splitlines()):
        if line.startswith(RESULT_MARK):
            return [Result(**d) for d in json.loads(line[len(RESULT_MARK):])]
    return None


def run_worker(task: str, env: dict[str, str], *args: str, timeout: int = 300) -> list[Result]:
    """scripts.checks.worker를 별도 프로세스로 실행하고 결과를 받는다 (앱 import 오염 방지)."""
    code, out = run(
        [python_exe(), "-m", "scripts.checks.worker", task, *args], ROOT, env, timeout
    )
    results = parse_worker_results(out)
    if results is None:
        return [Result(f"worker:{task}", FAIL, f"결과를 받지 못함(종료 코드 {code})\n{tail(out)}")]
    return results


# ---------------------------------------------------------------- 임시 Postgres
def _pg_bin(name: str) -> str | None:
    exe = name + (".exe" if os.name == "nt" else "")
    found = shutil.which(name)
    if found:
        return found
    roots = [
        *sorted(Path("/opt/homebrew/opt").glob("postgresql@*/bin"), reverse=True),
        *sorted(Path("/usr/local/opt").glob("postgresql@*/bin"), reverse=True),
        *sorted(Path("/usr/lib/postgresql").glob("*/bin"), reverse=True),
        *sorted(Path("C:/Program Files/PostgreSQL").glob("*/bin"), reverse=True),
    ]
    for root in roots:
        if (root / exe).exists():
            return str(root / exe)
    return None


@dataclass
class TempPostgres:
    """검사 전용 Postgres 클러스터를 임시 폴더에 띄운다. 끝나면 반드시 종료·삭제한다."""

    base: Path
    port: int = 0
    _sock_dir: Path | None = None
    _started: bool = False
    _env: dict = field(default_factory=dict)

    @staticmethod
    def available() -> bool:
        return all(_pg_bin(n) for n in ("initdb", "pg_ctl"))

    def start(self) -> None:
        initdb, pg_ctl = _pg_bin("initdb"), _pg_bin("pg_ctl")
        assert initdb and pg_ctl
        data = self.base / "pgdata"
        self.port = free_port()
        self._sock_dir = Path(tempfile.mkdtemp(prefix="dpg"))  # 유닉스 소켓 경로 길이(≈100자) 제한 때문에 짧게
        self._env = os.environ.copy()
        if sys.platform == "darwin":
            self._env["LC_ALL"] = "en_US.UTF-8"  # 없으면 macOS에서 postmaster가 시작 직후 종료한다

        code, out = run(
            [initdb, "-D", str(data), "-A", "trust", "-U", "didim", "--no-locale", "-E", "UTF8"],
            self.base, self._env,
        )
        if code != 0:
            raise RuntimeError(f"initdb 실패: {tail(out)}")

        opts = f"-p {self.port} -c listen_addresses=127.0.0.1 -c fsync=off"
        if os.name != "nt":
            opts += f" -c unix_socket_directories={self._sock_dir}"
        code, out = run(
            [pg_ctl, "-D", str(data), "-o", opts, "-l", str(self.base / "pg.log"), "-w", "start"],
            self.base, self._env, timeout=60,
        )
        if code != 0:
            log = (self.base / "pg.log")
            raise RuntimeError(f"pg_ctl start 실패: {tail(out)}\n{tail(log.read_text(errors='replace') if log.exists() else '')}")
        self._started = True
        atexit.register(self.stop)

    def url(self, dbname: str) -> str:
        return f"postgresql+psycopg://didim@127.0.0.1:{self.port}/{dbname}"

    def create_db(self, dbname: str) -> str:
        # psycopg는 백엔드 venv에만 있으므로 그 파이썬으로 실행한다.
        code, out = run(
            [
                python_exe(), "-c",
                "import psycopg,sys;"
                "c=psycopg.connect(sys.argv[1],autocommit=True);"
                "c.execute('CREATE DATABASE \"'+sys.argv[2]+'\"')",
                f"postgresql://didim@127.0.0.1:{self.port}/postgres", dbname,
            ],
            self.base, self._env,
        )
        if code != 0:
            raise RuntimeError(f"DB 생성 실패: {tail(out)}")
        return self.url(dbname)

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        pg_ctl = _pg_bin("pg_ctl")
        if pg_ctl:
            run([pg_ctl, "-D", str(self.base / "pgdata"), "-m", "immediate", "stop"], self.base, self._env, timeout=60)
        if self._sock_dir:
            shutil.rmtree(self._sock_dir, ignore_errors=True)


def wait_http(url: str, seconds: float = 20.0) -> bool:
    import urllib.request

    end = time.time() + seconds
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:  # noqa: S310 (로컬 주소)
                return r.status < 500
        except Exception:
            time.sleep(0.3)
    return False
