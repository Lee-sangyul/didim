"""프런트 정적 분석(의존성 없음). tsc가 못 잡는, 과거에 실제로 사고가 났던 유형만 본다."""
from __future__ import annotations

import re
from pathlib import Path

from .core import FRONTEND

SRC = FRONTEND / "src"

# CSS 규칙이 없어도 되는 클래스(상태 표시·스크립트 훅 등). 필요하면 근거와 함께 추가한다.
UNSTYLED_OK: set[str] = {
    # 인라인 style={{...}}로만 꾸며진 재생성 UI. CSS로 옮기면 이 목록에서 지운다 (R015).
    "regenerate-btn",
    "version-nav",
}


def _strip_css(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"url\([^)]*\)", "", text)
    return re.sub(r"@import[^;]*;", "", text)


def css_classes() -> set[str]:
    found: set[str] = set()
    for path in (SRC / "styles").glob("*.css"):
        found |= set(re.findall(r"\.([A-Za-z_][\w-]*)", _strip_css(path.read_text("utf-8"))))
    return found


def _class_name_exprs(source: str):
    """className="..." 과 className={...}(중괄호 균형) 식을 순서대로 낸다."""
    for m in re.finditer(r"className=", source):
        i = m.end()
        if source[i] in "\"'":
            j = source.index(source[i], i + 1)
            yield source[i + 1 : j]
        elif source[i] == "{":
            depth, j = 0, i
            while j < len(source):
                depth += (source[j] == "{") - (source[j] == "}")
                j += 1
                if depth == 0:
                    break
            yield source[i + 1 : j - 1]


def used_classes() -> dict[str, set[str]]:
    """클래스 -> 쓰인 파일들. 동적 부분(${...})은 버리고 정적 토큰만 취한다."""
    used: dict[str, set[str]] = {}
    for path in SRC.glob("*.tsx"):
        for expr in _class_name_exprs(path.read_text("utf-8")):
            literals = re.findall(r"`([^`]*)`|\"([^\"]*)\"|'([^']*)'", expr)
            chunks = [next(x for x in lit if x != "") for lit in literals if any(lit)] or [expr]
            for chunk in chunks:
                chunk = re.sub(r"\$\{[^}]*\}", " ", chunk)
                for token in chunk.split():
                    if re.fullmatch(r"[A-Za-z_][\w-]*", token) and not token.endswith("-"):
                        used.setdefault(token, set()).add(path.name)
    return used


def undefined_classes() -> dict[str, list[str]]:
    defined = css_classes() | UNSTYLED_OK
    return {c: sorted(f) for c, f in sorted(used_classes().items()) if c not in defined}


def dead_state() -> list[str]:
    """useState의 값 또는 setter가 선언 외에 쓰이지 않는 경우 (미완성 기능의 흔적)."""
    problems: list[str] = []
    for path in SRC.glob("*.tsx"):
        text = path.read_text("utf-8")
        for m in re.finditer(r"const \[(\w+),\s*(set\w+)\]\s*=\s*useState", text):
            value, setter = m.group(1), m.group(2)
            if len(re.findall(rf"\b{setter}\b", text)) == 1:
                problems.append(f"{path.name}: {setter}() 호출 없음 -> {value}가 변하지 않음")
            elif len(re.findall(rf"\b{value}\b", text)) == 1:
                problems.append(f"{path.name}: {value}를 읽는 곳 없음 ({setter}만 호출)")
    return problems


def send_min_length() -> int | None:
    """App.tsx에서 전송 버튼이 막히는 최소 글자 수(`input.trim().length < N`)."""
    text = (SRC / "App.tsx").read_text("utf-8")
    m = re.search(r"input\.trim\(\)\.length\s*<\s*(\d+)", text)
    return int(m.group(1)) if m else None


def inline_style_count() -> int:
    """JSX 인라인 style={{ ... }} 개수. 디자인 토큰·다크 모드와 어긋나기 쉬워 줄여 가는 지표."""
    return sum(len(re.findall(r"style=\{\{", p.read_text("utf-8"))) for p in SRC.glob("*.tsx"))
