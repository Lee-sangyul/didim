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


# ---------------------------------------------------------------- 답변 다시 생성 (R010)
from fastapi import HTTPException  # noqa: E402

from app.schemas.cases import MessagePublic  # noqa: E402


class SeqStream:
    """호출될 때마다 다른 답변을 내보낸다."""

    def __init__(self, text):
        self.text_stream = iter([text])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _mock_llm(monkeypatch, answers):
    answers = iter(answers)

    class Client:
        def __init__(self, **_):
            self.messages = SimpleNamespace(stream=lambda **kw: SeqStream(next(answers)))

    monkeypatch.setattr(chat_service, "Anthropic", Client)
    monkeypatch.setattr(chat_service, "find_citations", lambda *a, **k: [])
    monkeypatch.setattr(
        chat_service, "assess_with_claude",
        lambda *a, **k: {"risk_level": 40, "countermeasures": "조치."},
    )


def _regen(session, case, message_id):
    session.expire_all()  # 저장은 별도 세션에서 일어난다. 운영에서는 요청마다 새 세션이므로 같은 조건
    return chat_service.start_regeneration(session, case, message_id)


def _first_answer(session, case):
    turn = chat_service.start_turn(session, case, "학부모가 협박했습니다.")
    events(turn)
    return session.exec(
        select(Message).where(Message.case_id == case.id, Message.role == "assistant")
        .order_by(Message.id.desc())
    ).first()


def test_regenerate_adds_version_without_new_user_message(env, monkeypatch):
    engine, session, case = env
    _mock_llm(monkeypatch, ["첫 답변", "두 번째 답변", "세 번째 답변"])
    reply = _first_answer(session, case)

    for _ in range(2):
        turn = _regen(session, case, reply.id)
        result = events(turn)
        assert result[-1]["type"] == "done"
        assert result[-1]["assessment"]["message_id"] == reply.id

    with Session(engine) as s:
        msgs = list(s.exec(select(Message).where(Message.case_id == case.id).order_by(Message.id)))
        assert [m.role for m in msgs] == ["user", "assistant"]  # 재생성해도 사용자 메시지가 늘지 않는다
        saved = s.get(Message, reply.id)
        assert saved.content == "세 번째 답변"
        public = MessagePublic.model_validate(saved)
        assert public.versions == ["첫 답변", "두 번째 답변", "세 번째 답변"]
        assert len(list(s.exec(select(Assessment)))) == 3  # 턴마다 평가 이력


def test_regenerate_uses_same_question_as_history(env, monkeypatch):
    _, session, case = env
    _mock_llm(monkeypatch, ["첫 답변", "다시"])
    reply = _first_answer(session, case)
    turn = chat_service.start_regeneration(session, case, reply.id)
    assert turn.prior[-1].role == "user" and turn.prior[-1].content == "학부모가 협박했습니다."
    assert all(m.id != reply.id for m in turn.prior)  # 옛 답변은 컨텍스트에 넣지 않는다


def test_regenerate_rejects_invalid_targets(env, monkeypatch):
    engine, session, case = env
    _mock_llm(monkeypatch, ["첫 답변", "둘째 질문의 답"])
    greeting = Message(case_id=case.id, role="assistant", content="안녕하세요")
    session.add(greeting)
    session.commit()
    session.refresh(greeting)

    def code(msg_id, c=case):
        with pytest.raises(HTTPException) as e:
            chat_service.start_regeneration(session, c, msg_id)
        return e.value.status_code

    assert code(greeting.id) == 400  # 앞에 사용자 질문이 없다
    assert code(999999) == 404

    first = _first_answer(session, case)
    chat_service.start_turn(session, case, "두 번째 질문입니다.")  # 이후 메시지가 생기면 최신이 아니다
    assert code(first.id) == 409

    other = Case(owner_id=case.owner_id)
    session.add(other)
    session.commit()
    session.refresh(other)
    assert code(first.id, other) == 404  # 다른 상담의 메시지


def test_regenerate_version_limit(env, monkeypatch):
    _, session, case = env
    _mock_llm(monkeypatch, ["a"] * 20)
    reply = _first_answer(session, case)
    for _ in range(chat_service.MAX_ANSWER_VERSIONS - 1):
        events(_regen(session, case, reply.id))
    with pytest.raises(HTTPException) as e:
        _regen(session, case, reply.id)
    assert e.value.status_code == 409


# ---------------------------------------------------------------- DB가 뒤처졌을 때의 채팅 오류 문구 (R016)
def test_chat_error_message_names_outdated_db_not_api_key(env, monkeypatch):
    from app.db_migrate import OUTDATED_MESSAGE

    _, session, case = env
    _mock_llm(monkeypatch, ["답변"])

    def boom(*a, **k):
        raise RuntimeError("relation does not exist")

    monkeypatch.setattr(chat_service, "_save_result", boom)
    turn = chat_service.start_turn(session, case, "학부모가 협박했습니다.")

    monkeypatch.setattr(chat_service, "outdated_by", lambda exc, engine: True)
    assert events(turn)[-1] == {"type": "error", "message": OUTDATED_MESSAGE}

    _mock_llm(monkeypatch, ["답변"])
    monkeypatch.setattr(chat_service, "outdated_by", lambda exc, engine: False)
    assert "API 키" in events(turn)[-1]["message"]  # DB 문제가 아니면 기존 안내 그대로
