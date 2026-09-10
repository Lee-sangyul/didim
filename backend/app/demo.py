from dataclasses import dataclass

from .risk import bucket


@dataclass
class DemoAssessment:
    level: str
    score: int
    category: str
    rationale: str
    actions: list[str]


def assess(text: str) -> DemoAssessment:
    high = ("죽", "찾아가", "가만두지", "폭행", "칼", "해치", "협박")
    caution = ("반복", "매일", "욕설", "민원", "신고", "SNS", "녹음", "문자")
    h = sum(word in text for word in high)
    c = sum(word in text for word in caution)
    if h >= 2:
        score = min(100, 90 + h * 3)
    elif h == 1:
        score = min(89, 60 + c * 6)
    elif c >= 2:
        score = min(59, 30 + c * 6)
    elif c == 1:
        score = 30
    else:
        score = 15
    level = bucket(score)
    if level == "emergency":
        return DemoAssessment(level, score, "긴급 위협", "구체적 위협과 반복성이 함께 감지되어 즉각적인 안전 확보와 기관 대응이 필요합니다.", ["현재 안전을 최우선으로 확보하세요.", "112 등 긴급기관에 즉시 연락하세요.", "관리자에게 즉시 보고하고 기록을 원본 상태로 보존하세요."])
    if level == "danger":
        return DemoAssessment(level, score, "폭언·위협", "구체적 위협 또는 반복성이 감지되어 즉각적인 기관 대응 검토가 필요합니다.", ["현재 안전을 먼저 확보하세요.", "관리자에게 즉시 보고하고 기록을 원본 상태로 보존하세요.", "급박한 위험이면 112 등 긴급기관에 연락하세요."])
    if level == "caution":
        return DemoAssessment(level, score, "악성민원·반복 연락", "반복 연락이나 위협성 표현 가능성이 있어 개인 대응보다 공식 절차 전환이 권장됩니다.", ["문자·통화·메일을 날짜순으로 정리하고 백업하세요.", "학교 관리자에게 서면으로 보고하세요.", "공식 연락 채널을 안내하고 개인 연락은 최소화하세요.", "교원단체 또는 법률지원 검토를 요청하세요."])
    return DemoAssessment(level, score, "일반 상담", "현재 입력만으로 급박한 위험은 뚜렷하지 않지만 기록을 남기며 경과를 관찰하는 것이 좋습니다.", ["사실관계와 시점을 메모하세요.", "추가 상황이 생기면 관리자와 공유하세요.", "법적 판단이 필요하면 전문가 검토를 받으세요."])


def demo_reply(text: str, assessment: DemoAssessment) -> str:
    actions = "\n".join(f"{i + 1}. {item}" for i, item in enumerate(assessment.actions))
    return f"많이 힘드셨겠습니다. 입력한 내용에서 **{assessment.category}** 관련 신호를 확인했습니다.\n\n{assessment.rationale}\n\n{actions}\n\n정확한 판단을 위해 해당 표현이 문자·메일·녹음처럼 객관적인 기록으로 남아 있는지도 확인해 주세요. 이 결과는 일반적인 안내이며 최종 법률 판단이 아닙니다."

