"""가입 증빙 문서 보관 정책과 만료 문서 삭제.

정책: 심사(승인·거절)가 끝난 시점부터 RETENTION_YEARS년 보관한 뒤 삭제한다.
심사 전에는 신청 시점부터 같은 기간을 상한으로 둔다(심사가 영원히 안 되어도 남지 않게).
삭제는 purge_expired_documents()가 한다 — 서버가 자동으로 부르지 않으므로
`python -m scripts.purge_registration_documents`를 정기적으로(예: 하루 한 번) 실행해야 한다.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlmodel import Session, select

from ..models import RegistrationApplication, RegistrationDocument, now_iso
from .storage_service import delete_registration_document

RETENTION_YEARS = 5


def retention_deadline(start: datetime) -> datetime:
    """start로부터 RETENTION_YEARS년 뒤. 2월 29일이면 윤년이 아닌 해에는 2월 28일."""
    try:
        return start.replace(year=start.year + RETENTION_YEARS)
    except ValueError:
        return start.replace(year=start.year + RETENTION_YEARS, day=28)


def deadline_iso_from(start_iso: str) -> str:
    return retention_deadline(datetime.fromisoformat(start_iso)).isoformat()


@dataclass
class PurgeReport:
    checked: int = 0
    deleted: int = 0
    failed: list[str] = field(default_factory=list)  # 삭제에 실패한 문서의 storage_path
    would_delete: list[str] = field(default_factory=list)  # dry-run일 때


def purge_expired_documents(
    session: Session,
    now: datetime | None = None,
    dry_run: bool = False,
    delete_fn: Callable[[str], None] = delete_registration_document,
) -> PurgeReport:
    """보관 기간이 지난 증빙 문서를 Storage에서 지우고 deleted_at을 기록한다.

    한 문서가 실패해도 나머지는 계속한다. Storage 삭제가 성공한 뒤에만 deleted_at을 쓰므로
    실패한 문서는 다음 실행에서 다시 시도된다.
    """
    now = now or datetime.now(timezone.utc)
    report = PurgeReport()

    rows = session.exec(
        select(RegistrationDocument, RegistrationApplication)
        .join(
            RegistrationApplication,
            RegistrationApplication.id == RegistrationDocument.application_id,  # type: ignore[arg-type]
        )
        .where(RegistrationDocument.deleted_at.is_(None))  # type: ignore[union-attr]
    ).all()

    for document, application in rows:
        report.checked += 1
        due = application.document_delete_after

        if not due or datetime.fromisoformat(due) > now:
            continue

        if dry_run:
            report.would_delete.append(document.storage_path)
            continue

        try:
            delete_fn(document.storage_path)
        except Exception:
            report.failed.append(document.storage_path)
            continue

        document.deleted_at = now_iso()
        session.add(document)
        session.commit()
        report.deleted += 1

    return report
