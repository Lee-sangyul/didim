"""상담(Case) 목록·생성·메시지·평가 조회·삭제."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import Assessment, Attachment, Case, Message
from ..schemas.cases import (
    AssessmentPublic,
    CasePublic,
    CreateCase,
    MessagePublic,
)
from ..services.case_service import (
    assessment_public,
    case_public,
    get_owned_case,
)
from ..config import settings
from .auth import CurrentUserDependency

UPLOAD_DIR = settings.upload_dir

router = APIRouter()


@router.get(
    "/api/cases",
    response_model=list[CasePublic],
)
def list_cases(
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> list[CasePublic]:
    """
    현재 로그인한 사용자가 소유한 상담만 반환한다.
    """
    if current_user.id is None:
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다.",
        )

    cases = session.exec(
        select(Case)
        .where(
            Case.owner_id == current_user.id
        )
        .order_by(
            Case.updated_at.desc()
        )
    )

    return [
        case_public(item)
        for item in cases
    ]


@router.post(
    "/api/cases",
    response_model=CasePublic,
)
def create_case(
    body: CreateCase,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> CasePublic:
    """
    현재 로그인 사용자의 소유로 새 상담을 생성한다.
    """
    if current_user.id is None:
        raise HTTPException(
            status_code=401,
            detail="로그인이 필요합니다.",
        )

    case = Case(
        owner_id=current_user.id,
        title=body.title.strip() or "새 상담",
    )

    session.add(case)
    session.commit()
    session.refresh(case)

    greeting = Message(
        case_id=case.id or 0,
        role="assistant",
        content=(
            "안녕하세요. 겪고 계신 상황을 시간 순서대로 "
            "적어 주세요. 실명·전화번호 등 개인정보는 "
            "입력하지 않는 것이 좋습니다."
        ),
    )

    session.add(greeting)
    session.commit()

    return case_public(case)


@router.get(
    "/api/cases/{case_id}/messages",
    response_model=list[MessagePublic],
)
def messages(
    case_id: int,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> list[MessagePublic]:
    get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )

    items = session.exec(
        select(Message)
        .where(
            Message.case_id == case_id
        )
        .order_by(Message.id)
    )

    return [
        MessagePublic.model_validate(item)
        for item in items
    ]

@router.get(
    "/api/cases/{case_id}/assessments",
    response_model=list[AssessmentPublic],
)
def assessments(
    case_id: int,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> list[AssessmentPublic]:
    get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )

    items = session.exec(
        select(Assessment)
        .where(
            Assessment.case_id == case_id
        )
        .order_by(Assessment.id)
    )

    return [
        assessment_public(item)
        for item in items
    ]


@router.delete(
    "/api/cases/{case_id}",
    status_code=204,
)
def delete_case(
    case_id: int,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> None:
    case = get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )

    assessments_to_delete = session.exec(
        select(Assessment).where(
            Assessment.case_id == case_id
        )
    )

    for item in assessments_to_delete:
        session.delete(item)

    # 관계(relationship)가 없어 SQLAlchemy가 삭제 순서를 보장하지 않으므로,
    # 외래키 순서(평가 -> 메시지 -> 상담)대로 단계마다 flush한다.
    # (SQLite는 FK를 강제하지 않아 문제가 없지만 Postgres는 FK 위반으로 실패한다.)
    session.flush()

    attachments_to_delete = session.exec(
        select(Attachment).where(
            Attachment.case_id == case_id
        )
    )

    for attachment in attachments_to_delete:
        path = (
            UPLOAD_DIR
            / str(case_id)
            / attachment.stored_name
        )

        path.unlink(
            missing_ok=True,
        )

        session.delete(attachment)

    messages_to_delete = session.exec(
        select(Message).where(
            Message.case_id == case_id
        )
    )

    for message in messages_to_delete:
        session.delete(message)

    session.flush()

    session.delete(case)
    session.commit()
