import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from anthropic import Anthropic

JSON_DIR = Path(__file__).resolve().parents[2] / "json"

OUTPUT_TEMPLATE = {
    "risk_level": 0,
    "countermeasures": "",
    "based_law": ["clauses 1: ", "clauses 2: ", "clauses 3: "],
}


@lru_cache(maxsize=1)
def _program_config_text() -> str:
    return (JSON_DIR / "program_config.json").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _laws_text() -> str:
    return (JSON_DIR / "laws.json").read_text(encoding="utf-8")


def build_system_blocks() -> list[dict[str, Any]]:
    return [
        {
            "type": "text",
            "text": (
                "당신은 디딤(DIDIM)의 위험도 평가 엔진입니다. 아래 program_config.json에 정의된 역할, "
                "허용된 행동, 금지된 행동, 데이터 정책을 반드시 지키세요.\n\n" + _program_config_text()
            ),
        },
        {
            # 법령 데이터는 매 요청 동일하므로 프롬프트 캐싱으로 반복 호출 비용을 낮춘다.
            "type": "text",
            "text": (
                "아래는 참고 가능한 법령 데이터베이스(laws.json) 전체입니다. "
                "반드시 이 목록에 실제로 존재하는 조문만 근거로 사용하고, 존재하지 않는 법령·조항을 지어내지 마세요.\n\n"
                + _laws_text()
            ),
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": (
                "사용자 입력은 input.json 형식의 JSON으로 주어집니다. "
                "분석 결과는 아래 output.json 형식과 정확히 동일한 키만 가진 JSON 객체 하나만 출력하세요. "
                "설명, 마크다운, 코드블록 없이 순수 JSON 텍스트만 출력합니다. "
                "risk_level은 0~100 사이의 정수이며 상황이 심각할수록 높아야 합니다.\n\n"
                + json.dumps(OUTPUT_TEMPLATE, ensure_ascii=False)
            ),
        },
    ]


def build_input_payload(original_prompt: str, last_prompt: str) -> dict[str, Any]:
    return {
        "input_template_verseion": "1.0.0",
        "critical_level": "",
        "is_evidence_exists": False,
        "original_prompt": original_prompt,
        "last_prompt": last_prompt,
        "last_use_date": datetime.now(timezone.utc).isoformat(),
    }


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"```\s*$", "", text)
    return text.strip()


def split_countermeasures(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    lines = [line.strip() for line in re.split(r"\n+", text) if line.strip()]
    if len(lines) > 1:
        return [re.sub(r"^\d+[.)]\s*", "", line) for line in lines]
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return parts or [text]


def bucket(score: int) -> str:
    if score >= 90:
        return "emergency"
    if score >= 60:
        return "danger"
    if score >= 30:
        return "caution"
    return "low"


def assess_with_claude(client: Anthropic, model: str, original_prompt: str, last_prompt: str) -> dict[str, Any]:
    payload = build_input_payload(original_prompt, last_prompt)
    response = client.messages.create(
        model=model,
        max_tokens=1500,
        thinking={"type": "disabled"},
        system=build_system_blocks(),
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    raw = "".join(block.text for block in response.content if block.type == "text")
    data = json.loads(_strip_code_fence(raw))
    risk_level = max(0, min(100, int(data["risk_level"])))
    countermeasures = str(data.get("countermeasures", "")).strip()
    based_law = [str(item) for item in data.get("based_law", [])]
    return {"risk_level": risk_level, "countermeasures": countermeasures, "based_law": based_law}
