"""검색 스모크: python -m scripts.legal_smoke  (backend/ 에서 실행)"""
from sqlmodel import Session

from app.legal import retriever
from app.legal.db import legal_engine
from app.legal.models import Law

QUERIES = [
    ["폭언"],
    ["아동학대 신고"],
    ["교육활동 침해행위"],
    ["교육활동 침해행위", "조치"],
    ["학부모 민원"],
    ["교권보호위원회"],
    ["제15조"],
    ["제2조"],
    ["협박"],
    ["정당한 교육활동 아동학대"],
]

with Session(legal_engine) as s:
    for q in QUERIES:
        print(f"\n## {q}")
        for a in retriever.search(q, 8, session=s):
            law = s.get(Law, a.law_id)
            print(f"  {law.name[:14]:<14} {a.article_no:<8} {a.title or ''}")
