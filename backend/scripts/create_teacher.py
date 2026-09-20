from getpass import getpass

from sqlmodel import Session, select

from app.database import engine
from app.models import User
from app.security.password import hash_password
from app.services.auth_service import normalize_username


def main() -> None:
    print("디딤 교사 계정 생성")
    print()

    username = normalize_username(
        input("교사 아이디: ")
    )

    if len(username) < 3:
        raise ValueError(
            "교사 아이디는 3자 이상이어야 합니다."
        )

    name = input("교사 이름: ").strip()

    if not name:
        raise ValueError(
            "교사 이름은 비어 있을 수 없습니다."
        )

    password = getpass("교사 비밀번호: ")
    password_confirm = getpass("비밀번호 확인: ")

    if password != password_confirm:
        raise ValueError(
            "입력한 비밀번호가 서로 다릅니다."
        )

    if len(password) < 12:
        raise ValueError(
            "교사 비밀번호는 12자 이상이어야 합니다."
        )

    with Session(engine) as session:
        existing_user = session.exec(
            select(User).where(
                User.username == username
            )
        ).first()

        if existing_user is not None:
            raise ValueError(
                "이미 사용 중인 아이디입니다."
            )

        user = User(
            username=username,
            password_hash=hash_password(password),
            name=name,
            role="teacher",
            is_active=True,
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        print()
        print("교사 계정이 생성되었습니다.")
        print(f"사용자 번호: {user.id}")
        print(f"아이디: {user.username}")
        print(f"이름: {user.name}")
        print(f"권한: {user.role}")


if __name__ == "__main__":
    main()