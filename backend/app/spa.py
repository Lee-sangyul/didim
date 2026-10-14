"""빌드된 프런트(frontend/dist)를 백엔드가 직접 서빙한다 (launcher.py/배포 exe용).

개발 중에는 Vite(5173)가 화면을 주므로 dist가 없으면 아무것도 하지 않는다.
반드시 모든 API 라우터를 등록한 뒤에 호출해야 한다(catch-all 라우트가 있기 때문).
"""
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import ROOT


def default_dist() -> Path:
    # 점검 스크립트(scripts/check.py)가 임시 위치에 빌드한 산출물을 서빙할 때만 쓰는 지정
    override = os.environ.get("FRONTEND_DIST")
    if override:
        return Path(override)

    # PyInstaller로 묶인 exe는 실행 파일 옆의 frontend/dist를 쓴다.
    base = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else ROOT
    return base / "frontend" / "dist"


def mount_frontend(app: FastAPI, dist: Path | None = None) -> bool:
    dist = (dist or default_dist()).resolve()
    index = dist / "index.html"

    if not index.is_file():
        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # 없는 API 경로가 index.html(200)로 보이면 오류를 알아채기 어렵다.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = (dist / full_path).resolve()

        # dist 바깥 파일(.env 등)은 절대 내보내지 않는다.
        if full_path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)

        # 그 외는 클라이언트 라우팅(/register, /admin 등)이므로 index.html
        return FileResponse(index)

    return True
