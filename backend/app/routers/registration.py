import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import (
    RegistrationApplication,
    RegistrationDocument,
    User,
)
from ..security.password import hash_password
from ..services.storage_service import (
    StorageOperationError,
    delete_registration_document,
    upload_registration_document,
)


router = APIRouter(
    prefix="/api/registration",
    tags=["registration"],
)

SessionDependency = Annotated[
    Session,
    Depends(get_session),
]

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def current_time_iso() -> str:
    return datetime.now(
        timezone.utc,
    ).isoformat()


@router.post(
    "/applications",
    status_code=status.HTTP_201_CREATED,
)
async def create_registration_application(
    session: SessionDependency,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    name: Annotated[str, Form()],
    school_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    document: Annotated[UploadFile, File()],
    phone: Annotated[str | None, Form()] = None,
) -> dict:
    normalized_username = username.strip().lower()
    normalized_name = name.strip()
    normalized_school_name = school_name.strip()
    normalized_email = email.strip().lower()
    normalized_phone = (
        phone.strip()
        if phone and phone.strip()
        else None
    )

    if not 3 <= len(normalized_username) <= 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="아이디는 3자 이상 50자 이하로 입력하세요.",
        )

    if not normalized_username.replace(
        "_",
        "",
    ).isalnum():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "아이디에는 영문, 숫자, "
                "밑줄만 사용할 수 있습니다."
            ),
        )

    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비밀번호는 8자 이상이어야 합니다.",
        )

    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이름을 입력하세요.",
        )

    if not normalized_school_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="학교명을 입력하세요.",
        )

    if (
        "@" not in normalized_email
        or normalized_email.startswith("@")
        or normalized_email.endswith("@")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="올바른 이메일 주소를 입력하세요.",
        )

    existing_user = session.exec(
        select(User).where(
            User.username == normalized_username,
        )
    ).first()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디입니다.",
        )

    existing_application = session.exec(
        select(RegistrationApplication).where(
            RegistrationApplication.username
            == normalized_username,
            RegistrationApplication.status
            == "pending",
        )
    ).first()

    if existing_application is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 심사 중인 신청이 있습니다.",
        )

    content_type = (
        document.content_type
        or ""
    ).lower()

    extension = ALLOWED_CONTENT_TYPES.get(
        content_type,
    )

    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "PDF, JPG, PNG 문서만 "
                "제출할 수 있습니다."
            ),
        )

    content = await document.read(
        settings.registration_max_upload_bytes
        + 1
    )

    await document.close()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="제출한 문서가 비어 있습니다.",
        )

    if (
        len(content)
        > settings.registration_max_upload_bytes
    ):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="문서 크기는 최대 10MB입니다.",
        )

    file_hash = hashlib.sha256(
        content,
    ).hexdigest()

    storage_path = (
        "applications/"
        f"{uuid.uuid4().hex}{extension}"
    )

    original_filename = (
        Path(document.filename or f"document{extension}")
        .name
    )

    delete_after = (
        datetime.now(timezone.utc)
        + timedelta(days=30)
    ).isoformat()

    application = RegistrationApplication(
        username=normalized_username,
        password_hash=hash_password(password),
        name=normalized_name,
        school_name=normalized_school_name,
        email=normalized_email,
        phone=normalized_phone,
        status="pending",
        document_delete_after=delete_after,
        created_at=current_time_iso(),
        updated_at=current_time_iso(),
    )

    uploaded = False

    try:
        upload_registration_document(
            storage_path=storage_path,
            content=content,
            content_type=content_type,
        )

        uploaded = True

        session.add(application)
        session.flush()

        if application.id is None:
            raise RuntimeError(
                "신청 번호를 생성하지 못했습니다."
            )

        registration_document = RegistrationDocument(
            application_id=application.id,
            original_filename=original_filename,
            storage_path=storage_path,
            content_type=content_type,
            size=len(content),
            sha256=file_hash,
        )

        session.add(registration_document)
        session.commit()
        session.refresh(application)

    except StorageOperationError as error:
        session.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    except Exception as error:
        session.rollback()

        if uploaded:
            try:
                delete_registration_document(
                    storage_path,
                )
            except StorageOperationError:
                pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="회원가입 신청을 저장하지 못했습니다.",
        ) from error

    return {
        "message": (
            "계정 발급 신청이 접수되었습니다. "
            "관리자 승인 후 로그인할 수 있습니다."
        ),
        "application_id": application.id,
        "status": application.status,
        "notice": (
            "현재 버전은 제출 문서의 진위 여부를 "
            "자동으로 확인하지 않습니다."
        ),
    }
    