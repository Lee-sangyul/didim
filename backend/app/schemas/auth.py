from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """
    로그인 요청 데이터.
    """

    username: str = Field(
        min_length=3,
        max_length=50,
    )

    password: str = Field(
        min_length=1,
        max_length=256,
    )


class UserResponse(BaseModel):
    """
    프런트엔드에 공개할 사용자 정보.

    password_hash 같은 민감한 정보는 절대 포함하지 않는다.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    username: str
    name: str
    role: str
    is_active: bool


class LoginResponse(BaseModel):
    """
    로그인 성공 응답.
    """

    message: str
    user: UserResponse


class LogoutResponse(BaseModel):
    """
    로그아웃 성공 응답.
    """

    message: str