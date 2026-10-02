import json
from pathlib import Path

import pytest

from app.legal.parser import (
    LawLookupError,
    parse_articles,
    parse_law,
    select_current_law,
)

FIX = Path(__file__).parent.parent / "fixtures" / "legal"


def load(name):
    return json.loads((FIX / name).read_text("utf-8"))


def by_no(articles):
    return {a.article_no: a for a in articles}


def test_select_current_law_exact_match():
    law = select_current_law(load("search_교육기본법.json"), "교육기본법")
    assert law["법령일련번호"] == "285783"


def test_select_ignores_middle_dot_variant_and_substrings():
    resp = load("search_교육기본법.json")
    # 같은 이름이 포함된 다른 법령('…기본법')은 선택되지 않는다
    assert select_current_law(resp, "교육기본법")["법령명한글"] == "교육기본법"


def test_select_errors_on_zero_or_ambiguous():
    resp = load("search_교육기본법.json")
    with pytest.raises(LawLookupError):
        select_current_law(resp, "없는법")
    dup = {"LawSearch": {"law": [resp["LawSearch"]["law"][0]] * 2}}
    with pytest.raises(LawLookupError):
        select_current_law(dup, "교육기본법")
    historic = {"LawSearch": {"law": [{**resp["LawSearch"]["law"][0], "현행연혁코드": "연혁"}]}}
    with pytest.raises(LawLookupError):
        select_current_law(historic, "교육기본법")


def test_law_meta_and_chapter_titles_excluded():
    law = parse_law(load("law_교육기본법.json"))
    assert law.name == "교육기본법"
    assert law.effective_date == "2026-05-06"
    assert law.promulgation_no == "21608"
    assert len(law.articles) == 44  # 47단위 - 전문 3
    assert all(a.article_no.startswith("제") for a in law.articles)
    assert not any("총칙" in a.body[:10] for a in law.articles)


def test_article_without_paragraphs():
    a = by_no(parse_law(load("law_교육기본법.json")).articles)["제1조"]
    assert a.title == "(목적)"
    assert a.body.startswith("제1조(목적) 이 법은")


def test_article_with_paragraphs_keeps_header_and_newlines():
    a = by_no(parse_law(load("law_교육기본법.json")).articles)["제5조"]
    lines = a.body.split("\n")
    assert lines[0] == "제5조(교육의 자주성 등)"
    assert lines[1].startswith("① 국가와")
    assert len(lines) == 4


def test_branch_number_and_items():
    a = by_no(parse_law(load("law_교육기본법.json")).articles)["제17조의2"]
    assert a.article_no == "제17조의2"
    assert "\n  1. 양성평등의식과" in a.body


def test_deleted_article_skipped_and_paragraph_only_ho_dict():
    arts = by_no(parse_articles(load("law_초중등교육법_trimmed.json")))
    assert "제35조" not in arts  # "제35조 삭제 <2004.1.29>"
    # 항이 dict(호만 있음)인 조문: 본문이 호까지 포함
    assert "제2조" in arts and "  1. 초등학교" in arts["제2조"].body
    # 부분 삭제(항 단위)는 조문을 남긴다
    assert "제32조" in arts
    assert "제10조의2" in arts


def test_sub_items_indentation():
    a = by_no(parse_articles(load("law_아동학대특례법_trimmed.json")))["제2조"]
    assert "\n  4. \"아동학대범죄\"" in a.body
    assert "\n    가. 「형법」" in a.body
    assert "정당한 교육활동과 학생생활지도는 아동학대로 보지 아니한다" in a.body
