from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import RegistrationApplication, RegistrationDocument
from app.services import retention as r

NOW = datetime(2031, 6, 1, tzinfo=timezone.utc)


def test_deadline_is_five_years_and_handles_leap_day():
    assert r.RETENTION_YEARS == 5
    assert r.retention_deadline(datetime(2026, 3, 10, tzinfo=timezone.utc)).year == 2031
    leap = r.retention_deadline(datetime(2024, 2, 29, tzinfo=timezone.utc))  # 2029는 윤년이 아님
    assert (leap.year, leap.month, leap.day) == (2029, 2, 28)
    assert r.deadline_iso_from("2026-03-10T09:00:00+00:00").startswith("2031-03-10")


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def add_doc(session, name, due: datetime, deleted=False):
    app = RegistrationApplication(
        username=name, password_hash="x", name=name, school_name="s", email=f"{name}@x.test",
        document_delete_after=due.isoformat(),
    )
    session.add(app)
    session.commit()
    session.refresh(app)
    doc = RegistrationDocument(
        application_id=app.id, original_filename="a.pdf", storage_path=f"applications/{name}.pdf",
        content_type="application/pdf", size=1, sha256=name,
        deleted_at="2030-01-01T00:00:00+00:00" if deleted else None,
    )
    session.add(doc)
    session.commit()
    return doc


def test_purge_deletes_only_expired_and_marks_deleted_at(session):
    add_doc(session, "expired", NOW - timedelta(days=1))
    add_doc(session, "future", NOW + timedelta(days=1))
    add_doc(session, "already", NOW - timedelta(days=9), deleted=True)
    removed = []

    report = r.purge_expired_documents(session, now=NOW, delete_fn=removed.append)

    assert removed == ["applications/expired.pdf"]
    assert (report.checked, report.deleted, report.failed) == (2, 1, [])
    docs = {d.sha256: d for d in session.exec(select(RegistrationDocument))}
    assert docs["expired"].deleted_at and docs["future"].deleted_at is None


def test_dry_run_changes_nothing_and_failures_are_retried_later(session):
    add_doc(session, "expired", NOW - timedelta(days=1))
    calls = []

    dry = r.purge_expired_documents(session, now=NOW, dry_run=True, delete_fn=calls.append)
    assert dry.would_delete == ["applications/expired.pdf"] and calls == []

    def boom(path):
        raise RuntimeError("storage down")

    bad = r.purge_expired_documents(session, now=NOW, delete_fn=boom)
    assert bad.failed == ["applications/expired.pdf"] and bad.deleted == 0
    # Storage 삭제가 실패하면 deleted_at을 쓰지 않으므로 다음 실행에서 다시 시도된다
    assert session.exec(select(RegistrationDocument)).one().deleted_at is None
    assert r.purge_expired_documents(session, now=NOW, delete_fn=calls.append).deleted == 1
