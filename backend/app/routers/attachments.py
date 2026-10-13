"""상담 첨부파일 업로드·목록·다운로드·삭제."""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import Attachment
from ..schemas.cases import AttachmentPublic
from ..services.case_service import get_owned_case
from .auth import CurrentUserDependency

UPLOAD_DIR = settings.upload_dir
MAX_UPLOAD_BYTES = settings.max_upload_bytes

router = APIRouter()


@router.post(
    "/api/cases/{case_id}/attachments",
    response_model=AttachmentPublic,
)
async def upload_attachment(
    case_id: int,
    current_user: CurrentUserDependency,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> AttachmentPublic:
    get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )

    original_name = Path(
        file.filename or "attachment"
    ).name

    stored_name = (
        f"{uuid.uuid4().hex}_{original_name}"
    )

    case_dir = (
        UPLOAD_DIR
        / str(case_id)
    )

    case_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        case_dir
        / stored_name
    )

    size = 0

    with destination.open("wb") as output:
        while chunk := await file.read(
            1024 * 1024
        ):
            size += len(chunk)

            if size > MAX_UPLOAD_BYTES:
                output.close()

                destination.unlink(
                    missing_ok=True,
                )

                raise HTTPException(
                    status_code=413,
                    detail=(
                        "파일 크기는 설정된 최대 크기를 "
                        "초과할 수 없습니다."
                    ),
                )

            output.write(chunk)

    attachment = Attachment(
        case_id=case_id,
        filename=original_name,
        stored_name=stored_name,
        content_type=(
            file.content_type
            or "application/octet-stream"
        ),
        size=size,
    )

    session.add(attachment)
    session.commit()
    session.refresh(attachment)

    return AttachmentPublic.model_validate(
        attachment
    )


@router.get(
    "/api/cases/{case_id}/attachments",
    response_model=list[AttachmentPublic],
)
def list_attachments(
    case_id: int,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> list[AttachmentPublic]:
    get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )

    attachments = session.exec(
        select(Attachment)
        .where(
            Attachment.case_id == case_id
        )
        .order_by(Attachment.id)
    )

    return [
        AttachmentPublic.model_validate(item)
        for item in attachments
    ]


@router.get(
    "/api/cases/{case_id}/attachments/{attachment_id}/download"
)
def download_attachment(
    case_id: int,
    attachment_id: int,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> FileResponse:
    get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )

    attachment = session.get(
        Attachment,
        attachment_id,
    )

    if (
        attachment is None
        or attachment.case_id != case_id
    ):
        raise HTTPException(
            status_code=404,
            detail="파일을 찾을 수 없습니다.",
        )

    path = (
        UPLOAD_DIR
        / str(case_id)
        / attachment.stored_name
    )

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail="파일을 찾을 수 없습니다.",
        )

    return FileResponse(
        path=path,
        filename=attachment.filename,
        media_type=attachment.content_type,
    )


@router.delete(
    "/api/cases/{case_id}/attachments/{attachment_id}",
    status_code=204,
)
def delete_attachment(
    case_id: int,
    attachment_id: int,
    current_user: CurrentUserDependency,
    session: Session = Depends(get_session),
) -> None:
    get_owned_case(
        case_id=case_id,
        session=session,
        current_user=current_user,
    )

    attachment = session.get(
        Attachment,
        attachment_id,
    )

    if (
        attachment is None
        or attachment.case_id != case_id
    ):
        raise HTTPException(
            status_code=404,
            detail="파일을 찾을 수 없습니다.",
        )

    path = (
        UPLOAD_DIR
        / str(case_id)
        / attachment.stored_name
    )

    path.unlink(
        missing_ok=True,
    )

    session.delete(attachment)
    session.commit()
