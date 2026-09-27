from functools import lru_cache

from supabase import Client, create_client

from ..config import settings


class StorageConfigurationError(RuntimeError):
    """Supabase Storage 설정이 없거나 잘못된 경우."""


class StorageOperationError(RuntimeError):
    """Supabase Storage 작업에 실패한 경우."""


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    if not settings.has_supabase_storage:
        raise StorageConfigurationError(
            "Supabase Storage 설정이 없습니다. "
            "SUPABASE_URL과 SUPABASE_SECRET_KEY를 확인하세요."
        )

    return create_client(
        settings.supabase_url,
        settings.supabase_secret_key,
    )


def upload_registration_document(
    storage_path: str,
    content: bytes,
    content_type: str,
) -> None:
    """
    회원가입 증빙 문서를 비공개 버킷에 업로드한다.

    같은 경로의 파일이 이미 존재하면 덮어쓰지 않는다.
    """
    try:
        client = get_supabase_client()

        client.storage.from_(
            settings.supabase_storage_bucket
        ).upload(
            path=storage_path,
            file=content,
            file_options={
                "content-type": content_type,
                "upsert": "false",
            },
        )

    except Exception as error:
        raise StorageOperationError(
            "증빙 문서를 저장하지 못했습니다."
        ) from error


def download_registration_document(
    storage_path: str,
) -> bytes:
    """
    관리자가 검토할 증빙 문서를 비공개 버킷에서 읽는다.
    """
    try:
        client = get_supabase_client()

        content = client.storage.from_(
            settings.supabase_storage_bucket
        ).download(
            storage_path,
        )

        return bytes(content)

    except Exception as error:
        raise StorageOperationError(
            "증빙 문서를 불러오지 못했습니다."
        ) from error


def delete_registration_document(
    storage_path: str,
) -> None:
    """
    보관 기간이 끝난 증빙 문서를 삭제한다.
    """
    try:
        client = get_supabase_client()

        client.storage.from_(
            settings.supabase_storage_bucket
        ).remove(
            [storage_path],
        )

    except Exception as error:
        raise StorageOperationError(
            "증빙 문서를 삭제하지 못했습니다."
        ) from error