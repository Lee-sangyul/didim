from datetime import datetime, timezone

import pytest
from sqlmodel import Session, create_engine

from app.legal import retriever
from app.legal.db import legal_registry
from app.legal.models import Article, Law


@pytest.fixture()
def session():
    """합성 데이터 전용 인메모리 DB. 실제 법령 내용이 아니다."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    legal_registry.metadata.create_all(engine)
    with Session(engine) as s:
        law = Law(
            name="테스트법",
            law_mst="1",
            source_url="https://example.test/law",
            fetched_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        s.add(law)
        s.commit()
        s.refresh(law)
        rows = [
            ("제1조", "(목적)", "이 법은 가나다 보호를 목적으로 한다."),
            ("제15조", "(조치)", "라마바 침해행위에 대하여 조치를 한다."),
            ("제15조의2", "(특례)", "사아자 신고 의무를 정한다."),
            ("제20조", "(폭언)", "폭언 및 협박 행위를 금지한다."),
        ]
        for no, title, body in rows:
            s.add(
                Article(
                    law_id=law.id,
                    article_no=no,
                    title=title,
                    body=body,
                    search_text=f"{law.name} {no} {title} {body}",
                )
            )
        s.commit()
        retriever.rebuild_index(s)
        yield s
