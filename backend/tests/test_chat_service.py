"""채팅 파이프라인(Claude 경로)을 외부 호출 없이 검증한다."""
import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.legal.schemas import Citation
from app.models import Assessment, Case, Message, User
from app.services import chat_service


class FakeStream:
    text_stream = iter(["안녕", "하세요"])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeClient:
    def __init__(self, **_):
        self.messages = SimpleNamespace(stream=lambda **kw: FakeStream())


@pytest.fixture()
def env(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(chat_service, "engine", engine)
    monkeypatch.setattr(chat_service, "Anthropic", FakeClient)
    monkeypatch.setattr(chat_service, "is_demo", lambda: False)

    with Session(engine) as session:
        user = User(username="u", password_hash="x", name="u")
        session.add(user)
        session.commit()
        case = Case(owner_id=user.id)
        session.add(case)
        session.commit()
        session.refresh(case)
        yield engine, session, case


def events(turn):
    return [json.loads(e[6:]) for e in chat_service.stream_events(turn)]


def test_claude_path_saves_reply_assessment_and_citations(env, monkeypatch):
    engine, session, case = env
    citation = Citation(
        article_id=1, law_name="테스트법", article_no="제1조", title="(목적)",
        text="원문", reason="이유", source_url="u", as_of="2026-01-01",
    )
    monkeypatch.setattr(chat_service, "find_citations", lambda *a, **k: [citation])
    monkeypatch.setattr(
        chat_service,
        "assess_with_claude",
        lambda *a, **k: {"risk_level": 70, "countermeasures": "조치 하나.\n조치 둘."},
    )

    turn = chat_service.start_turn(session, case, "학부모가 협박했습니다.")
    result = events(turn)

    assert [e["type"] for e in result] == ["delta", "delta", "done"]
    done = result[-1]["assessment"]
    assert done["level"] == "danger" and done["score"] == 70
    assert done["based_law"] == ["테스트법 제1조"]
    assert done["citations"][0]["text"] == "원문"

    with Session(engine) as s:
        assert [m.role for m in s.exec(select(Message))] == ["user", "assistant"]
        saved = s.exec(select(Assessment)).one()
        assert json.loads(saved.citations)[0]["article_no"] == "제1조"


def test_risk_assessment_failure_falls_back_without_failing_request(env, monkeypatch):
    _, session, case = env
    monkeypatch.setattr(chat_service, "find_citations", lambda *a, **k: [])

    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(chat_service, "assess_with_claude", boom)

    turn = chat_service.start_turn(session, case, "학부모가 협박했습니다.")
    result = events(turn)

    assert result[-1]["type"] == "done"
    assert result[-1]["assessment"]["citations"] == []


def test_case_removed_mid_stream_yields_error(env, monkeypatch):
    engine, session, case = env
    monkeypatch.setattr(chat_service, "find_citations", lambda *a, **k: [])
    monkeypatch.setattr(
        chat_service, "assess_with_claude",
        lambda *a, **k: {"risk_level": 10, "countermeasures": ""},
    )

    turn = chat_service.start_turn(session, case, "상황을 설명합니다.")
    turn.owner_id = 999  # 소유자가 달라진 경우와 동일하게 저장을 거부해야 한다

    assert events(turn)[-1] == {"type": "error", "message": "상담을 찾을 수 없습니다."}
