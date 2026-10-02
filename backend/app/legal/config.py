from pathlib import Path

from ..config import ROOT

LEGAL_DATA_DIR: Path = ROOT / "data" / "legal"
RAW_DIR: Path = LEGAL_DATA_DIR / "raw"
ARTICLES_JSON: Path = LEGAL_DATA_DIR / "articles.json"

# 수집 대상 법령(법령명은 국가법령정보센터 정식 명칭).
# 시행령·시행규칙을 추가하려면 이 리스트에 이름만 추가한다.
TARGET_LAWS: list[str] = [
    "교원의 지위 향상 및 교육활동 보호를 위한 특별법",
    "교육기본법",
    "초ㆍ중등교육법",
    "아동학대범죄의 처벌 등에 관한 특례법",
]

LAW_SERVICE_URL = "https://www.law.go.kr/법령/{name}"

# 검색·선택 단계 상수
CANDIDATE_K = 8
MAX_SELECTED = 3
MAX_QUERIES = 4
