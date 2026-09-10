from app.demo import assess
from app.privacy import mask_pii


def test_masks_contact_data():
    assert mask_pii("010-1234-5678 test@example.com") == "[전화번호] [이메일]"


def test_assessment_detects_threat():
    result = assess("매일 찾아가서 가만두지 않겠다고 협박했습니다")
    assert result.level == "emergency"


def test_assessment_low_path():
    result = assess("오늘 학부모님과 상담을 진행했습니다")
    assert result.level == "low"
    assert result.score < 30

