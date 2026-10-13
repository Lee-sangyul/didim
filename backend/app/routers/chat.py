"""상담 채팅(SSE 스트리밍). 실제 처리는 services/chat_service.py."""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from ..database import get_session
from ..schemas.cases import ChatInput
from ..services.case_service import get_owned_case
from ..services.chat_service import start_turn, stream_events
from .auth import CurrentUserDependency

router = APIRouter()


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
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
