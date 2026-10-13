"""상담 채팅(SSE 스트리밍). 실제 처리는 services/chat_service.py."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..database import get_session
from ..schemas.cases import ChatInput
from ..services.case_service import get_owned_case
from ..services.chat_service import (
    start_regeneration,
    start_turn,
    stream_events,
)
from .auth import CurrentUserDependency

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}


@router.post("/api/cases/{case_id}/chat")
def chat(
    case_id: int,
    body: ChatInput,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    case = get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )
    turn = start_turn(session, case, body.content)

    return StreamingResponse(
        stream_events(turn),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/api/cases/{case_id}/messages/{message_id}/regenerate")
def regenerate(
    case_id: int,
    message_id: int,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """마지막 답변을 다시 생성한다. 사용자 메시지를 새로 만들지 않고 답변 버전만 누적한다."""
    case = get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )
    turn = start_regeneration(session, case, message_id)

    return StreamingResponse(
        stream_events(turn),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
