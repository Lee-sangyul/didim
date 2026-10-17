"""DB 마이그레이션 상태 확인 / 적용. 어느 폴더에서 실행해도 같다.

    cd backend
    python -m scripts.migrate              # 상태만 본다 (DB를 바꾸지 않음)
    python -m scripts.migrate --upgrade    # 최신으로 올린다 (alembic upgrade head)

.env의 DATABASE_URL을 쓴다. 운영 DB를 가리키고 있으면 운영 DB가 바뀐다.
"""
import argparse

from app.database import engine
from app.db_migrate import schema_state, upgrade_head

MESSAGES = {
    "empty": "비어 있는 DB입니다. --upgrade로 스키마를 만드세요 (서버를 시작해도 자동으로 만들어집니다).",
    "ready": "최신 상태입니다.",
    "outdated": "코드보다 뒤처져 있습니다. --upgrade로 올리세요.",
    "unmanaged": "테이블은 있지만 alembic 이력이 없습니다. 자동으로 올리지 않습니다.",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--upgrade", action="store_true", help="최신 마이그레이션까지 적용")
    args = parser.parse_args()

    if engine.dialect.name == "sqlite":
        print("SQLite는 서버가 시작할 때 테이블을 직접 만듭니다. 마이그레이션이 필요 없습니다.")
        return 0

    state = schema_state(engine)
    print(f"DB 리비전: {state['current']} / 코드 head: {state['head']} → {state['status']}")
    print(MESSAGES[state["status"]])

    if not args.upgrade:
        return 0 if state["status"] == "ready" else 1

    if state["status"] == "unmanaged":
        print("중단: alembic 이력이 없는 DB는 자동으로 올리지 않습니다.")
        return 1

    upgrade_head(engine)
    print(f"완료: {schema_state(engine)['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
