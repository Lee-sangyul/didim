import json
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from ..legal.schemas import Citation
from ..models import Assessment, Case
from ..routers.auth import CurrentUserDependency
from ..schemas.cases import AssessmentPublic, CasePublic


def _load_json_list(raw: str | None) -> list[Any]:
    """DB에 JSON 문자열로 저장한 리스트를 읽는다. 깨진 값은 빈 리스트로 본다."""
    try:
        value = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    return value if isinstance(value, list) else []


def case_public(case: Case) -> CasePublic:
    return CasePublic(
        id=case.id or 0,
        title=case.title,
        category=case.category,
        risk_level=case.risk_level,
        risk_score=case.risk_score,
        based_law=_load_json_list(case.based_law),
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def assessment_public(item: Assessment) -> AssessmentPublic:
    try:
        citations = [Citation(**c) for c in _load_json_list(item.citations)]
    except (TypeError, ValueError):
        citations = []

    return AssessmentPublic(
        id=item.id or 0,
        case_id=item.case_id,
        message_id=item.message_id,
        risk_level=item.risk_level,
        risk_score=item.risk_score,
        category=item.category,
        rationale=item.rationale,
        based_law=_load_json_list(item.based_law),
        actions=_load_json_list(item.actions),
        citations=citations,
        created_at=item.created_at,
    )


def get_owned_case(
    case_id: int,
    session: Session,
    current_user: CurrentUserDependency,
) -> Case:
    """
    현재 로그인 사용자가 소유한 상담을 반환한다.

    다른 사용자의 상담도 존재 여부를 숨기기 위해
    소유자가 다르면 403이 아니라 404를 반환한다.
    """
    case = session.get(Case, case_id)

    if (
        case is None
        or current_user.id is None
        or case.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=404,
            detail="상담을 찾을 수 없습니다.",
        )

    return case
