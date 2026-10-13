from app.risk import build_system_blocks


def test_system_blocks_build_without_missing_data_files():
    """risk.py가 삭제된 json/laws.json을 읽다 FileNotFoundError로 조용히 폴백되던 회귀 방지."""
    blocks = build_system_blocks()
    assert blocks and all(b["type"] == "text" and b["text"] for b in blocks)
    assert "based_law" not in blocks[-1]["text"]
