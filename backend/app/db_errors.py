"""DB가 코드보다 뒤처졌을 때의 요청 실패를 '설명 없는 500' 대신 명확한 503으로 바꾼다. (R016)

정책: 서버는 뒤처진 DB에서도 **기동한다**(결정). 대신 영향을 받는 요청만 실패시키되,
사용자에게는 이유를, 운영자에게는 로그로 해결 명령을 알려 준다. 마이그레이션을 적용하면 재시작 없이 복구된다.
"""
import logging
import time

from fastapi.responses import JSONResponse
from sqlalchemy.engine import Engine

from .db_migrate import OUTDATED_MESSAGE, live_state, outdated_by

logger = logging.getLogger(__name__)

_LOG_INTERVAL_SECONDS = 60.0
_last_logged = 0.0


def _log_outdated(engine: Engine) -> None:
    """같은 경고가 요청마다 쏟아지지 않게 1분에 한 번만 남긴다."""
    global _last_logged
    now = time.monotonic()

    if now - _last_logged < _LOG_INTERVAL_SECONDS:
        return

    _last_logged = now
    state = live_state(engine)
    logger.error(
        "DB가 코드보다 뒤처져 요청이 실패하고 있습니다 (DB %s, 코드 %s). "
        "`cd backend && python -m scripts.migrate --upgrade` 로 적용하세요. 적용하면 서버를 재시작하지 않아도 복구됩니다.",
        state.get("current"), state.get("head"),
    )


def outdated_db_response(exc: BaseException, engine: Engine) -> JSONResponse | None:
    """DB가 뒤처진 탓의 오류면 503 응답을, 아니면 None(=일반 오류로 처리)을 돌려준다."""
    if not outdated_by(exc, engine):
        return None

    _log_outdated(engine)
    return JSONResponse(
        status_code=503,
        content={"detail": OUTDATED_MESSAGE, "code": "db_outdated"},
        headers={"Retry-After": "60"},
    )
