"""국가법령정보센터 lawService.do (type=JSON) 응답 -> 조문 리스트. 순수 함수, 네트워크 없음.

응답 구조(실제 응답으로 확인):
- 법령.기본정보: 법령명_한글, 공포번호, 시행일자(YYYYMMDD)
- 법령.조문.조문단위[]: 조문여부("조문"|"전문"), 조문번호, 조문가지번호(선택),
  조문제목(선택), 조문내용, 항[](선택)
- 항은 리스트이거나, 항번호/항내용 없이 호만 있는 dict 하나로 올 수 있다.
  호/목도 같은 식으로 리스트 또는 단일 dict일 수 있어 _as_list로 정규화한다.
- 항이 없는 조문은 조문내용에 "제1조(목적) 본문..." 전체가 들어 있고,
  항이 있는 조문은 조문내용이 "제5조(제목)" 머리글뿐이며 본문은 항에 있다.
- 삭제 조문은 조문내용이 "제35조 삭제 <2004.1.29>" 형태이고 제목·항이 없다.
"""
import re
from dataclasses import dataclass
from typing import Any, Optional


class LawLookupError(Exception):
    """검색 결과가 0건이거나 모호할 때."""


@dataclass
class ParsedArticle:
    article_no: str
    title: Optional[str]
    body: str


@dataclass
class ParsedLaw:
    name: str
    promulgation_no: Optional[str]
    effective_date: Optional[str]  # YYYY-MM-DD
    articles: list[ParsedArticle]


_DELETED_RE = re.compile(r"^제\d+조(?:의\d+)?\s*삭제(?:\s*<[^>]*>)?\s*$")


def _as_list(value: Any) -> list[dict]:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def _normalize_name(name: str) -> str:
    # 공식 명칭은 가운뎃점으로 'ㆍ'(U+318D)를 쓴다. '·'(U+00B7)로 입력해도 같게 본다.
    return name.replace("·", "ㆍ").replace(" ", "")


def select_current_law(search_response: dict, name: str) -> dict:
    """검색 결과에서 법령명이 정확히 일치하는 '현행' 1건을 고른다.

    선택 기준: 법령명한글 == name (공백·가운뎃점 표기 차이 무시) AND 현행연혁코드 == "현행".
    부분 일치(예: '… 시행령')는 제외한다. 조건에 맞는 것이 정확히 1건이 아니면 중단한다.
    """
    laws = _as_list(search_response.get("LawSearch", {}).get("law"))
    matches = [
        law
        for law in laws
        if _normalize_name(law.get("법령명한글", "")) == _normalize_name(name)
        and law.get("현행연혁코드") == "현행"
    ]
    if len(matches) != 1:
        raise LawLookupError(
            f"'{name}' 현행 법령이 {len(matches)}건입니다 (정확히 1건이어야 함)"
        )
    return matches[0]


def format_date(yyyymmdd: Optional[str]) -> Optional[str]:
    if yyyymmdd and re.fullmatch(r"\d{8}", yyyymmdd):
        return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:]}"
    return None


def _article_no(unit: dict) -> str:
    no = f"제{unit['조문번호']}조"
    branch = unit.get("조문가지번호")
    return f"{no}의{branch}" if branch else no


def _article_body(unit: dict) -> str:
    lines = [unit.get("조문내용", "").strip()]
    for para in _as_list(unit.get("항")):
        if para.get("항내용"):
            lines.append(para["항내용"].strip())
        for item in _as_list(para.get("호")):
            lines.append("  " + item.get("호내용", "").strip())
            for sub in _as_list(item.get("목")):
                lines.append("    " + sub.get("목내용", "").strip())
    return "\n".join(line for line in lines if line.strip())


def parse_articles(detail: dict) -> list[ParsedArticle]:
    units = _as_list(detail["법령"]["조문"]["조문단위"])
    result: list[ParsedArticle] = []
    for unit in units:
        if unit.get("조문여부") != "조문":  # 장·절 제목 등 전문
            continue
        if _DELETED_RE.match(unit.get("조문내용", "").strip()):
            continue
        title = unit.get("조문제목")
        result.append(
            ParsedArticle(
                article_no=_article_no(unit),
                title=f"({title})" if title else None,
                body=_article_body(unit),
            )
        )
    return result


def parse_law(detail: dict) -> ParsedLaw:
    info = detail["법령"]["기본정보"]
    return ParsedLaw(
        name=info["법령명_한글"],
        promulgation_no=info.get("공포번호") or None,
        effective_date=format_date(info.get("시행일자")),
        articles=parse_articles(detail),
    )
