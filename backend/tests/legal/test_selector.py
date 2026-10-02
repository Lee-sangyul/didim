import json
from types import SimpleNamespace

from sqlmodel import select

from app.legal import retriever, selector
from app.legal.models import Article
from app.legal.service import build_queries


class FakeClient:
    def __init__(self, text=None, error=None):
        self.messages = SimpleNamespace(create=self._create)
        self._text, self._error = text, error

    def _create(self, **kwargs):
        if self._error:
            raise self._error
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self._text)])


def candidates(session):
    return list(session.exec(select(Article)))


def run(session, client):
    return selector.select_citations(client, "m", "요약", candidates(session), session)


def test_valid_selection_uses_db_text(session):
    target = candidates(session)[1]
    text = json.dumps({"selected": [{"article_id": target.id, "reason": "이유"}]})
    result = run(session, FakeClient(text))
    assert len(result) == 1
    assert result[0].text == target.body
    assert result[0].as_of == "2026-01-02"
    assert result[0].reason == "이유"


def test_invalid_duplicate_and_overflow_ids_dropped(session):
    ids = [a.id for a in candidates(session)]
    sel = [{"article_id": 9999, "reason": "x"}, {"article_id": "bad"}]
    sel += [{"article_id": i, "reason": "r"} for i in [ids[0], ids[0], *ids[1:]]]
    result = run(session, FakeClient("```json\n" + json.dumps({"selected": sel}) + "\n```"))
    assert [c.article_id for c in result] == ids[:3]


def test_all_invalid_gives_empty(session):
    text = json.dumps({"selected": [{"article_id": 9999, "reason": "x"}]})
    assert run(session, FakeClient(text)) == []


def test_bad_json_and_api_error_fall_back(session):
    assert run(session, FakeClient("not json")) == []
    assert run(session, FakeClient(error=RuntimeError("boom"))) == []


def test_no_candidates_skips_llm(session):
    assert selector.select_citations(FakeClient(error=RuntimeError()), "m", "s", [], session) == []


def test_build_queries():
    assert build_queries("폭언·위협", ["협박", "폭언"]) == ["폭언", "위협", "협박"]
    assert build_queries("일반 상담") == []
    assert len(build_queries("a b c d e")) == 4
