import json

from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.legal import retriever
from app.legal.bootstrap import ensure_legal_db


def write(path, laws):
    path.write_text(json.dumps({"laws": laws}, ensure_ascii=False), "utf-8")


def law(name, *articles):
    return {
        "name": name, "law_mst": "1", "promulgation_no": "1", "effective_date": "2026-01-01",
        "source_url": "https://example.test", "fetched_at": "2026-01-02T00:00:00",
        "articles": [{"article_no": no, "title": f"({title})", "body": body} for no, title, body in articles],
    }


def search(engine, query):
    with Session(engine) as s:
        return [a.article_no for a in retriever.search([query], 8, session=s)]


def test_builds_when_missing_skips_when_same_and_replaces_when_changed(tmp_path):
    src, engine = tmp_path / "articles.json", create_engine(f"sqlite:///{tmp_path / 'legal.db'}")
    write(src, [law("가법", ("제1조", "목적", "알파 베타 감마 보호"))])

    first = ensure_legal_db(engine, src)
    assert (first["status"], first["laws"], first["articles"]) == ("rebuilt", 1, 1)
    assert search(engine, "알파") == ["제1조"]

    assert ensure_legal_db(engine, src)["status"] == "ready"  # 같은 파일이면 다시 만들지 않는다

    write(src, [law("나법", ("제9조", "새조문", "델타 엡실론 신규"))])  # 가법이 사라지고 나법이 생김
    again = ensure_legal_db(engine, src)
    assert again["status"] == "rebuilt" and again["laws"] == 1
    assert search(engine, "델타") == ["제9조"]
    assert search(engine, "알파") == []  # 없어진 법령이 남지 않는다


def test_missing_source_and_broken_source_do_not_raise(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legal.db'}")
    assert ensure_legal_db(engine, tmp_path / "none.json")["status"] == "missing_source"

    bad = tmp_path / "articles.json"
    bad.write_text("{not json")
    assert ensure_legal_db(engine, bad)["status"] == "error"
