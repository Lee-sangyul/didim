"""보관 기간(5년)이 지난 가입 증빙 문서를 삭제한다.

    cd backend
    python -m scripts.purge_registration_documents --dry-run   # 지울 대상만 확인
    python -m scripts.purge_registration_documents             # 실제 삭제

운영에서는 하루 한 번 정도 정기 실행하도록 설정한다 (cron / Windows 작업 스케줄러).
.env의 DATABASE_URL·SUPABASE_*를 사용하므로 운영 데이터에 직접 영향이 있다.
"""
import argparse

from sqlmodel import Session

from app.database import engine
from app.services.retention import RETENTION_YEARS, purge_expired_documents


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="삭제하지 않고 대상만 출력")
    args = parser.parse_args()

    with Session(engine) as session:
        report = purge_expired_documents(session, dry_run=args.dry_run)

    print(f"보관 기간 {RETENTION_YEARS}년 / 확인한 문서 {report.checked}건")
    if args.dry_run:
        print(f"삭제 대상(dry-run) {len(report.would_delete)}건")
    else:
        print(f"삭제 {report.deleted}건, 실패 {len(report.failed)}건")
    for path in report.failed:
        print(f"  실패: {path}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
