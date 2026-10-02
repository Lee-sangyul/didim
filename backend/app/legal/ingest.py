"""법령 수집 CLI (수동 실행, 서버 요청 처리 중에는 호출하지 않는다).

    python -m app.legal.ingest              # 국가법령정보센터 API -> DB + articles.json
    python -m app.legal.ingest --from-json  # articles.json -> DB (API 키 불필요)

API 응답은 JSON(type=JSON)만 사용한다. 인증키는 환경변수 LAW_API_OC.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlmodel import Session, select

from ..config import settings
from . import retriever
from .config import ARTICLES_JSON, LAW_SERVICE_URL, RAW_DIR, TARGET_LAWS
from .db import legal_engine, legal_registry
from .models import Article, Law
from .parser import ParsedArticle, ParsedLaw, parse_law, select_current_law

API = "https://www.law.go.kr/DRF"


def _get(client: httpx.Client, path: str, **params: str) -> str:
    response = client.get(
        f"{API}/{path}",
        params={"OC": settings.law_api_oc, "type": "JSON", **params},
    )
    response.raise_for_status()
    return response.text


def _scrub(text: str) -> str:
    """응답(상세링크 등)에 인증키가 섞여 있을 수 있어 저장 전에 제거한다."""
    return text.replace(settings.law_api_oc, "REDACTED")


def fetch_law(client: httpx.Client, name: str) -> tuple[str, str, ParsedLaw]:
    """(law_mst, 본문 원본 텍스트, 파싱 결과). 모호하거나 없으면 LawLookupError."""
    search = json.loads(_get(client, "lawSearch.do", target="law", query=name))
    chosen = select_current_law(search, name)
    mst = chosen["법령일련번호"]
    raw = _get(client, "lawService.do", target="law", MST=mst)
    return mst, raw, parse_law(json.loads(raw))


def save_law(session: Session, parsed: ParsedLaw, mst: str, fetched_at: datetime) -> Law:
    """같은 법령을 재수집하면 기존 조문을 교체한다. commit은 호출자가 한 번에 한다."""
    law = session.exec(select(Law).where(Law.name == parsed.name)).first()
    if law is None:
        law = Law(name=parsed.name, law_mst=mst, source_url="", fetched_at=fetched_at)
    law.law_mst = mst
    law.promulgation_no = parsed.promulgation_no
    law.effective_date = parsed.effective_date
    law.source_url = LAW_SERVICE_URL.format(name=parsed.name)
    law.fetched_at = fetched_at
    session.add(law)
    session.flush()

    for old in session.exec(select(Article).where(Article.law_id == law.id)):
        session.delete(old)
    session.flush()

    for a in parsed.articles:
        session.add(
            Article(
                law_id=law.id,  # type: ignore[arg-type]
                article_no=a.article_no,
                title=a.title,
                body=a.body,
                search_text=" ".join(
                    p for p in (parsed.name, a.article_no, a.title, a.body) if p
                ),
            )
        )
    return law


def export_json(session: Session) -> int:
    laws = []
    for law in session.exec(select(Law).order_by(Law.id)):
        articles = session.exec(
            select(Article).where(Article.law_id == law.id).order_by(Article.id)
        )
        laws.append(
            {
                "name": law.name,
                "law_mst": law.law_mst,
                "promulgation_no": law.promulgation_no,
                "effective_date": law.effective_date,
                "source_url": law.source_url,
                "fetched_at": law.fetched_at.isoformat(),
                "articles": [
                    {"article_no": a.article_no, "title": a.title, "body": a.body}
                    for a in articles
                ],
            }
        )
    ARTICLES_JSON.parent.mkdir(parents=True, exist_ok=True)
    ARTICLES_JSON.write_text(
        json.dumps({"laws": laws}, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    return len(laws)


def load_from_json(session: Session) -> None:
    data = json.loads(ARTICLES_JSON.read_text("utf-8"))
    for item in data["laws"]:
        parsed = ParsedLaw(
            name=item["name"],
            promulgation_no=item["promulgation_no"],
            effective_date=item["effective_date"],
            articles=[],
        )
        parsed.articles = [ParsedArticle(**a) for a in item["articles"]]
        save_law(session, parsed, item["law_mst"], datetime.fromisoformat(item["fetched_at"]))


def report(session: Session) -> None:
    print("\n법령별 조문 수")
    for law in session.exec(select(Law).order_by(Law.id)):
        n = len(session.exec(select(Article.id).where(Article.law_id == law.id)).all())
        print(f"  {law.name}  MST={law.law_mst}  시행 {law.effective_date}  조문 {n}개")
    print("\n샘플 조문 (공식 원문과 대조용)")
    articles = session.exec(select(Article).order_by(Article.id)).all()
    for a in [articles[0], articles[len(articles) // 2], articles[-1]]:
        law = session.get(Law, a.law_id)
        print(f"\n--- {law.name if law else ''} {a.article_no} {a.title or ''}\n{a.body}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-json", action="store_true", help="articles.json으로 DB 복원")
    args = parser.parse_args(argv)

    legal_registry.metadata.create_all(legal_engine)

    with Session(legal_engine) as session:
        if args.from_json:
            load_from_json(session)
            session.commit()
        else:
            if not settings.law_api_oc:
                print("LAW_API_OC 환경변수가 필요합니다.", file=sys.stderr)
                return 1
            fetched_at = datetime.now(timezone.utc)
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            with httpx.Client(timeout=60) as client:
                # 하나라도 모호/실패하면 아무것도 적재하지 않고 중단한다.
                fetched: list[tuple[str, ParsedLaw]] = []
                for name in TARGET_LAWS:
                    mst, raw, parsed = fetch_law(client, name)
                    (RAW_DIR / f"{name}_{fetched_at:%Y-%m-%d}.json").write_text(_scrub(raw), "utf-8")
                    fetched.append((mst, parsed))
                    print(f"수집: {parsed.name} (MST {mst}, 조문 {len(parsed.articles)}개)")
            for mst, parsed in fetched:
                save_law(session, parsed, mst, fetched_at)
            session.commit()  # 전체 법령을 한 트랜잭션으로 교체

        count = retriever.rebuild_index(session)
        if not args.from_json:
            export_json(session)
        report(session)
        print(f"\nFTS 색인 {count}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
