from typing import Annotated, Optional

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlmodel import Session

from ..config import settings
from ..database import get_session
from ..models import User
from ..schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    UserResponse,
)
from ..security.session import (
    SESSION_COOKIE_NAME,
    SESSION_DURATION_DAYS,
)
from ..services.auth_service import (
    authenticate_user,
    create_auth_session,
    get_user_from_session_token,
    revoke_auth_session,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["auth"],
)


SessionDependency = Annotated[
    Session,
    Depends(get_session),
]

SessionCookie = Annotated[
    Optional[str],
    Cookie(alias=SESSION_COOKIE_NAME),
]


def get_current_user(
    session: SessionDependency,
    session_token: SessionCookie = None,
) -> User:
    """
    요청 쿠키를 확인하고 현재 로그인 사용자를 반환한다.
    """
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
        )

    user = get_user_from_session_token(
        session,
        session_token,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인 세션이 유효하지 않습니다.",
        )

    return user


CurrentUserDependency = Annotated[
    User,
    Depends(get_current_user),
]


@router.post(
    "/login",
    response_model=LoginResponse,
)
def login(
    payload: LoginRequest,
    response: Response,
    session: SessionDependency,
) -> LoginResponse:
    """
    아이디와 비밀번호로 로그인한다.
    """
    user = authenticate_user(
        session=session,
        username=payload.username,
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    session_token = create_auth_session(
        session=session,
        user=user,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_token,
        max_age=SESSION_DURATION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )

    return LoginResponse(
        message="로그인되었습니다.",
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
)
def logout(
    response: Response,
    session: SessionDependency,
    session_token: SessionCookie = None,
) -> LogoutResponse:
    """
    현재 로그인 세션을 폐기하고 쿠키를 삭제한다.
    """
    if session_token is not None:
        revoke_auth_session(
            session=session,
            token=session_token,
        )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )

    return LogoutResponse(
        message="로그아웃되었습니다.",
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    current_user: CurrentUserDependency,
) -> UserResponse:
    """
    현재 로그인한 사용자 정보를 반환한다.
    """
    return UserResponse.model_validate(
        current_user
    )