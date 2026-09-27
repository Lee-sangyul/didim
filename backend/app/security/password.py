from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    비밀번호를 Argon2 방식으로 해시한다.

    비밀번호 원문은 데이터베이스에 저장하지 않고,
    이 함수가 반환한 해시 문자열만 저장해야 한다.
    """
    if not password:
        raise ValueError("비밀번호는 비어 있을 수 없습니다.")

    return password_hasher.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    """
    입력된 비밀번호가 저장된 해시와 일치하는지 확인한다.
    """
    if not password or not password_hash:
        return False

    try:
        return password_hasher.verify(
            password,
            password_hash,
        )
    except UnknownHashError:
        return False