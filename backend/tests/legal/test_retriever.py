from app.legal import retriever


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
