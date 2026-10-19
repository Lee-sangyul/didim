"""디딤 API 회귀 테스트 (인증·상담·채팅·첨부·권한). 루트의 test_didim.py를 pytest로 옮긴 것이다.

실제 HTTP 요청을 TestClient로 보내 인증/DB 로직까지 검사한다. 임시 SQLite(외래키 강제)와 가짜 계정을 쓰고
외부 AI·법령 호출은 하지 않는다(환경은 tests/conftest.py가 격리한다).
프런트엔드, 실제 Claude 응답 품질, 운영 Postgres/Storage는 검사하지 않는다(scripts/check.py의 다른 단계가 맡는다).
"""
import json
import shutil
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, select

from app import models
from app.main import UPLOAD_DIR, app, engine
from app.security import password as passwords
from app.security import session as security
from app.services import chat_service

PASSWORD = "OnlyForTests!123"


@event.listens_for(engine, "connect")
def enable_foreign_keys(connection, _record):
    """SQLite도 Postgres처럼 외래키를 강제한다 (삭제 순서 버그를 로컬에서 잡기 위해)."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture()
def client():
    """각 테스트마다 테이블과 가짜 계정을 새로 만든다."""
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    hashed = passwords.hash_password(PASSWORD)
    with Session(engine) as session:
        for username, active in [("teacher_a", True), ("teacher_b", True), ("inactive", False)]:
            session.add(models.User(username=username, password_hash=hashed, name="테스트 교사", is_active=active))
        session.commit()

    # 외부 호출이 추가되더라도 데모 테스트에서 사용되면 실패한다 (R014: 호출이 일어나는 chat_service를 패치한다).
    with TestClient(app) as test_client, \
            patch.object(chat_service, "Anthropic", side_effect=AssertionError("외부 AI 호출 발생")), \
            patch.object(chat_service, "find_citations", side_effect=AssertionError("외부 법령 호출 발생")):
        yield test_client


# ---------------------------------------------------------------- 도우미
def login(client, username="teacher_a"):
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return response


def create_case(client, title="자동 테스트"):
    response = client.post("/api/cases", json={"title": title})
    assert response.status_code == 200
    return response.json()["id"]


def chat(client, case_id, content):
    response = client.post(f"/api/cases/{case_id}/chat", json={"content": content})
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
    assert events, "SSE 이벤트 없음"
    assert not any(item.get("type") == "error" for item in events), "SSE 오류 이벤트"
    assert sum(item.get("type") == "done" for item in events) == 1
    assert events[-1]["type"] == "done"
    answer = "".join(item["text"] for item in events if item["type"] == "delta").strip()
    assert answer
    return events[-1]["assessment"], answer


def upload(client, case_id):
    content = b"didim-test-evidence\n"
    response = client.post(
        f"/api/cases/{case_id}/attachments", files={"file": ("evidence.txt", content, "text/plain")}
    )
    assert response.status_code == 200
    assert response.json()["size"] == len(content)
    return response.json()["id"], content


# ---------------------------------------------------------------- 인증
def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "mode": "demo", "environment": "test"}


def test_unauthenticated_requests(client):
    for method, path, body in [
        ("GET", "/api/auth/me", None),
        ("GET", "/api/cases", None),
        ("POST", "/api/cases", {"title": "test"}),
        ("POST", "/api/cases/1/chat", {"content": "엄"}),
    ]:
        assert client.request(method, path, json=body).status_code == 401, path


def test_invalid_login(client):
    for username, password in [("teacher_a", "wrong"), ("missing", PASSWORD), ("inactive", PASSWORD)]:
        response = client.post("/api/auth/login", json={"username": username, "password": password})
        assert response.status_code == 401, username


def test_login_cookie_and_me(client):
    response = login(client)
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "teacher_a"
    assert "password_hash" not in me.json()


def test_session_token_is_hashed(client):
    login(client)
    token = client.cookies.get(security.SESSION_COOKIE_NAME)
    assert token
    with Session(engine) as session:
        stored = session.exec(select(models.AuthSession)).one()
        assert stored.token_hash != token
        assert stored.token_hash == security.hash_session_token(token)


def test_logout_revokes_old_cookie(client):
    login(client)
    old_token = client.cookies.get(security.SESSION_COOKIE_NAME)
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set(security.SESSION_COOKIE_NAME, old_token)
    assert client.get("/api/auth/me").status_code == 401


def test_expired_session(client):
    login(client)
    with Session(engine) as session:
        record = session.exec(select(models.AuthSession)).one()
        record.expires_at = "2000-01-01T00:00:00+00:00"
        session.add(record)
        session.commit()
    assert client.get("/api/auth/me").status_code == 401


# ---------------------------------------------------------------- 상담
def test_create_list_greeting(client):
    login(client)
    case_id = create_case(client, "  테스트 상담  ")
    cases = client.get("/api/cases").json()
    assert len(cases) == 1
    assert cases[0]["id"] == case_id
    assert cases[0]["title"] == "테스트 상담"
    messages = client.get(f"/api/cases/{case_id}/messages").json()
    assert len(messages) == 1
    assert messages[0]["role"] == "assistant"


def test_blank_title_fallback(client):
    login(client)
    create_case(client, "   ")
    assert client.get("/api/cases").json()[0]["title"] == "새 상담"


def test_single_character_chat(client):
    login(client)
    case_id = create_case(client)
    assessment, answer = chat(client, case_id, "엄")
    messages = client.get(f"/api/cases/{case_id}/messages").json()
    assert messages[-2]["content"] == "엄"
    assert messages[-1]["content"] == answer
    stored = client.get(f"/api/cases/{case_id}/assessments").json()
    assert len(stored) == 1
    assert stored[0]["risk_score"] == assessment["score"]
    assert stored[0]["message_id"] == messages[-1]["id"]


def test_chat_validation(client):
    login(client)
    case_id = create_case(client)
    for payload in [{"content": ""}, {"content": "가" * 8001}, {}, {"content": None}]:
        response = client.post(f"/api/cases/{case_id}/chat", json=payload)
        assert response.status_code == 422, f"length={len(payload.get('content') or '')}"
    assert len(client.get(f"/api/cases/{case_id}/messages").json()) == 1
    assert client.get(f"/api/cases/{case_id}/assessments").json() == []


def test_demo_risk_levels(client):
    login(client)
    for text, level, score in [
        ("안녕하세요", "low", 15), ("매일 욕설", "caution", 42), ("협박", "danger", 60), ("칼로 폭행", "emergency", 96),
    ]:
        case_id = create_case(client)
        result, _ = chat(client, case_id, text)
        assert (result["level"], result["score"]) == (level, score), level
        assert result["actions"], level


# ---------------------------------------------------------------- 권한·첨부
def test_other_user_cannot_access_case(client):
    login(client)
    case_id = create_case(client)
    attachment_id, _ = upload(client, case_id)
    client.post("/api/auth/logout")
    login(client, "teacher_b")
    assert client.get("/api/cases").json() == []
    prefix = f"/api/cases/{case_id}"
    requests = [
        ("GET", prefix + "/messages", {}),
        ("GET", prefix + "/assessments", {}),
        ("GET", prefix + "/attachments", {}),
        ("POST", prefix + "/chat", {"json": {"content": "엄"}}),
        ("POST", prefix + "/attachments", {"files": {"file": ("x.txt", b"x", "text/plain")}}),
        ("GET", prefix + f"/attachments/{attachment_id}/download", {}),
        ("DELETE", prefix + f"/attachments/{attachment_id}", {}),
        ("DELETE", prefix, {}),
    ]
    for method, path, kwargs in requests:
        assert client.request(method, path, **kwargs).status_code == 404, f"{method} {path}"
    client.post("/api/auth/logout")
    login(client)
    assert len(client.get(prefix + "/messages").json()) == 1
    assert len(client.get(prefix + "/attachments").json()) == 1


def test_attachment_round_trip_delete(client):
    login(client)
    case_id = create_case(client)
    attachment_id, content = upload(client, case_id)
    prefix = f"/api/cases/{case_id}/attachments"
    assert len(client.get(prefix).json()) == 1
    response = client.get(f"{prefix}/{attachment_id}/download")
    assert response.status_code == 200
    assert response.content == content
    assert client.delete(f"{prefix}/{attachment_id}").status_code == 204
    assert client.get(prefix).json() == []
    assert client.get(f"{prefix}/{attachment_id}/download").status_code == 404


def test_attachment_wrong_case(client):
    login(client)
    first, second = create_case(client), create_case(client)
    attachment_id, _ = upload(client, first)
    prefix = f"/api/cases/{second}/attachments/{attachment_id}"
    assert client.get(prefix + "/download").status_code == 404
    assert client.delete(prefix).status_code == 404


def test_oversized_upload_has_no_record_or_file(client):
    login(client)
    case_id = create_case(client)
    response = client.post(
        f"/api/cases/{case_id}/attachments",
        files={"file": ("big.bin", b"x" * (1024 * 1024 + 1), "application/octet-stream")},
    )
    assert response.status_code == 413
    assert client.get(f"/api/cases/{case_id}/attachments").json() == []
    assert list((UPLOAD_DIR / str(case_id)).glob("*")) == []


def test_delete_case_cascades(client):
    login(client)
    case_id = create_case(client)
    chat(client, case_id, "엄")
    upload(client, case_id)
    assert client.delete(f"/api/cases/{case_id}").status_code == 204
    assert client.get("/api/cases").json() == []
    assert client.get(f"/api/cases/{case_id}/messages").status_code == 404
    with Session(engine) as session:
        for model in [models.Message, models.Assessment, models.Attachment]:
            assert list(session.exec(select(model).where(model.case_id == case_id))) == [], model.__name__
    assert list((UPLOAD_DIR / str(case_id)).glob("*")) == []


def test_missing_case(client):
    login(client)
    for method, suffix, kwargs in [
        ("GET", "/messages", {}), ("GET", "/assessments", {}), ("GET", "/attachments", {}),
        ("DELETE", "", {}), ("POST", "/chat", {"json": {"content": "엄"}}),
    ]:
        assert client.request(method, "/api/cases/999999" + suffix, **kwargs).status_code == 404, f"{method} {suffix}"
