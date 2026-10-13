"""채팅 한 턴의 처리: 사건 분석 -> 근거 조문 검색 -> 답변 스트리밍 -> 위험도 평가 -> 저장.

라우터(routers/chat.py)는 요청 검증만 하고, 실제 흐름은 이 모듈에 있다.
"""
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic
from sqlmodel import Session, select

from ..config import settings
from ..database import engine
from ..demo import DemoAssessment, assess, demo_reply
from ..legal.schemas import Citation
from ..legal.service import find_citations
from ..models import Assessment, Case, Message, now_iso
from ..privacy import mask_pii
from ..risk import assess_with_claude, bucket, split_countermeasures

SYSTEM = """당신은 교권 침해 상담 도우미 '디딤'입니다. 한국어로 차분하고 지지적으로 답하세요. 법률 자문이나 확정 판단을 하지 마세요. 제공되지 않은 법령 조항을 지어내지 마세요. 개인정보 최소화, 증거 원본 보존, 관리자 보고, 교원단체·법률 전문가 검토 같은 절차를 안내하세요. 학생에게 해가 되는 조언, 은폐, 보복, 불법행위를 돕지 마세요. 즉각적인 신체 위험이 있으면 안전 확보와 긴급기관 연락을 먼저 권고하세요."""

HISTORY_LIMIT = 12  # Claude에 보내는 최근 메시지 수
ANSWER_MAX_TOKENS = 1400
DEFAULT_TITLE = "새 상담"
TITLE_MAX_CHARS = 28


def sse(payload: dict[str, Any]) -> str:
    """Server-Sent Events 한 건으로 직렬화한다."""
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


@dataclass
class ChatTurn:
    """요청 처리 시점에 확정되는 한 턴의 입력."""

    case_id: int
    owner_id: int | None
    original: str
    masked: str
    demo_assessment: DemoAssessment
    prior: list[Message]


@dataclass
class _Run:
    """스트리밍 중 누적되는 결과."""

    assessment: DemoAssessment
    chunks: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    @property
    def based_law(self) -> list[str]:
        # 근거 조문은 DB 원문 기반 citations에서 만든다 (LLM이 쓰지 않는다).
        return [f"{c.law_name} {c.article_no}" for c in self.citations]


def is_demo() -> bool:
    return settings.demo_mode or not settings.anthropic_api_key


def start_turn(session: Session, case: Case, content: str) -> ChatTurn:
    """사용자 메시지를 저장하고 상담 요약(분류·위험도·제목)을 갱신한다."""
    original = content.strip()
    masked = mask_pii(original)
    demo_assessment = assess(masked)

    session.add(Message(case_id=case.id or 0, role="user", content=original))

    case.category = demo_assessment.category
    case.risk_level = demo_assessment.level
    case.risk_score = demo_assessment.score
    case.updated_at = now_iso()

    if case.title == DEFAULT_TITLE:
        case.title = masked[:TITLE_MAX_CHARS] + (
            "…" if len(masked) > TITLE_MAX_CHARS else ""
        )

    session.add(case)
    session.commit()

    prior = list(
        session.exec(
            select(Message)
            .where(Message.case_id == case.id)
            .order_by(Message.id)  # type: ignore[arg-type]
        )
    )

    return ChatTurn(
        case_id=case.id or 0,
        owner_id=case.owner_id,
        original=original,
        masked=masked,
        demo_assessment=demo_assessment,
        prior=prior,
    )


def _system_prompt(citations: list[Citation]) -> str:
    if not citations:
        return SYSTEM

    return (
        SYSTEM
        + "\n\n[참고 조문 - 공식 원문. 아래 조문만 근거로 언급하세요.]\n"
        + "\n\n".join(
            f"{c.law_name} {c.article_no} {c.title or ''}\n{c.text}"
            for c in citations
        )
    )


def _demo_deltas(turn: ChatTurn) -> Iterator[str]:
    answer = demo_reply(turn.masked, turn.demo_assessment)
    for part in answer.split(" "):
        yield part + " "


def _claude_deltas(turn: ChatTurn, run: _Run) -> Iterator[str]:
    """Claude 답변을 스트리밍하고, 끝나면 위험도 평가로 run.assessment를 갱신한다."""
    client = Anthropic(api_key=settings.anthropic_api_key)
    model = settings.anthropic_model

    history = [
        {"role": m.role, "content": mask_pii(m.content)}
        for m in turn.prior[-HISTORY_LIMIT:]
    ]

    run.citations = find_citations(
        client, model, turn.demo_assessment.category, turn.masked
    )

    with client.messages.stream(
        model=model,
        max_tokens=ANSWER_MAX_TOKENS,
        system=_system_prompt(run.citations),
        messages=history,
    ) as stream:
        yield from stream.text_stream

    # 위험도 평가가 실패해도 답변은 이미 나갔으므로 데모 평가로 폴백한다.
    try:
        first_user = next(
            (m.content for m in turn.prior if m.role == "user"),
            turn.original,
        )
        result = assess_with_claude(
            client, model, mask_pii(first_user), turn.masked
        )
        run.assessment = DemoAssessment(
            bucket(result["risk_level"]),
            result["risk_level"],
            turn.demo_assessment.category,
            result["countermeasures"] or turn.demo_assessment.rationale,
            split_countermeasures(result["countermeasures"])
            or turn.demo_assessment.actions,
        )
    except Exception as exc:
        print(f"risk assessment fallback ({turn.case_id}): {exc}")


def _save_result(turn: ChatTurn, run: _Run) -> bool:
    """답변·평가를 저장한다. 그 사이 상담이 사라졌거나 소유자가 다르면 False."""
    final = "".join(run.chunks).strip()
    based_law = json.dumps(run.based_law, ensure_ascii=False)

    with Session(engine) as session:
        case = session.get(Case, turn.case_id)

        if (
            case is None
            or turn.owner_id is None
            or case.owner_id != turn.owner_id
        ):
            return False

        case.risk_level = run.assessment.level
        case.risk_score = run.assessment.score
        case.category = run.assessment.category
        case.based_law = based_law

        reply = Message(case_id=turn.case_id, role="assistant", content=final)
        session.add(case)
        session.add(reply)
        session.commit()
        session.refresh(reply)

        session.add(
            Assessment(
                case_id=turn.case_id,
                message_id=reply.id,
                risk_level=run.assessment.level,
                risk_score=run.assessment.score,
                category=run.assessment.category,
                rationale=run.assessment.rationale,
                based_law=based_law,
                actions=json.dumps(run.assessment.actions, ensure_ascii=False),
                citations=json.dumps(
                    [c.model_dump() for c in run.citations],
                    ensure_ascii=False,
                ),
            )
        )
        session.commit()

    return True


def stream_events(turn: ChatTurn) -> Iterator[str]:
    """채팅 응답 SSE 이벤트(delta -> done 또는 error)를 만든다."""
    run = _Run(assessment=turn.demo_assessment)

    try:
        deltas = _demo_deltas(turn) if is_demo() else _claude_deltas(turn, run)

        for text in deltas:
            run.chunks.append(text)
            yield sse({"type": "delta", "text": text})

        if not _save_result(turn, run):
            yield sse({"type": "error", "message": "상담을 찾을 수 없습니다."})
            return

        yield sse(
            {
                "type": "done",
                "assessment": {
                    **run.assessment.__dict__,
                    "based_law": run.based_law,
                    "citations": [c.model_dump() for c in run.citations],
                },
            }
        )

    except Exception:
        yield sse(
            {
                "type": "error",
                "message": (
                    "AI 응답 중 오류가 발생했습니다. "
                    "설정과 API 키를 확인하세요."
                ),
            }
        )
