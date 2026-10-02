from sqlmodel import select

from app.legal import retriever
from app.legal.models import Article, Law


def nos(articles):
    return [a.article_no for a in articles]


def test_trigram_term(session):
    assert nos(retriever.search(["침해행위"], session=session)) == ["제15조"]


def test_short_term_falls_back_to_like(session):
    assert "제20조" in nos(retriever.search(["폭언"], session=session))


def test_article_no_direct_lookup_and_branch(session):
    assert nos(retriever.search(["제15조"], session=session))[0] == "제15조"
    assert nos(retriever.search(["제15조의2"], session=session)) == ["제15조의2"]


def test_dedup_and_k(session):
    result = retriever.search(["폭언", "협박", "폭언 협박"], k=1, session=session)
    assert nos(result) == ["제20조"]


def test_no_match_and_empty(session):
    assert retriever.search(["없는단어들"], session=session) == []
    assert retriever.search([], session=session) == []
    assert retriever.search(["   "], session=session) == []


def test_special_chars_do_not_crash(session):
    assert retriever.search(['"', "%", "a_b"], session=session) == []


def _add(session, rows):
    """conftest 데이터에 합성 조문을 더하고 색인을 다시 만든다."""
    law_id = session.exec(select(Law.id)).first()
    for no, title, body in rows:
        session.add(
            Article(law_id=law_id, article_no=no, title=title, body=body, search_text=f"{no} {title} {body}")
        )
    session.commit()
    retriever.rebuild_index(session)


def test_law_name_is_not_indexed(session):
    # 법령명이 색인되면 그 법의 모든 조문이 매칭된다
    assert retriever.search(["테스트법"], session=session) == []


def test_title_match_beats_body_frequency(session):
    _add(
        session,
        [
            ("제30조", "(차카타 침해행위)", "차카타 침해행위란 다음을 말한다."),
            ("제31조", "(신고)", "차카타 침해행위 차카타 침해행위 차카타 침해행위를 신고한다."),
        ],
    )
    assert nos(retriever.search(["차카타 침해행위"], session=session))[0] == "제30조"


def test_short_term_query_is_not_crowded_out(session):
    # 3글자 이상 검색어(bm25)의 점수가 커도 2글자 검색어(LIKE) 결과가 후보에 남아야 한다.
    # 무관한 조문을 섞어 bm25의 IDF가 실제 코퍼스처럼 커지게 한다.
    _add(
        session,
        [(f"제{40 + i}조", "(차카타 침해행위)", "차카타 침해행위 " * (i + 1)) for i in range(10)]
        + [(f"제{100 + i}조", "(기타)", f"무관한 조문 {i}") for i in range(30)]
        + [("제60조", "(폭행)", "사람을 폭행한 자는 처벌한다.")],
    )
    assert "제60조" in nos(retriever.search(["차카타 침해행위", "폭행"], k=4, session=session))
