"""프런트 정적 분석(의존성 없음). tsc가 못 잡는, 과거에 실제로 사고가 났던 유형만 본다."""
from __future__ import annotations

import re
from pathlib import Path

from .core import FRONTEND

SRC = FRONTEND / "src"


def source_files(*suffixes: str):
    """src 아래 모든 소스 파일 (하위 폴더 포함). 파일을 폴더로 나눠도 점검에서 빠지지 않게 한다."""
    suffixes = suffixes or (".ts", ".tsx")
    return sorted(p for p in SRC.rglob("*") if p.suffix in suffixes and not p.name.endswith(".d.ts"))

# CSS 규칙이 없어도 되는 클래스(상태 표시·스크립트 훅 등). 필요하면 근거와 함께 추가한다.
UNSTYLED_OK: set[str] = set()


def _strip_css(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"url\([^)]*\)", "", text)
    return re.sub(r"@import[^;]*;", "", text)


def css_classes() -> set[str]:
    found: set[str] = set()
    for path in (SRC / "styles").rglob("*.css"):  # styles/app/ 같은 하위 폴더 포함
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
    for path in source_files(".tsx"):
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
    for path in source_files():
        text = path.read_text("utf-8")
        for m in re.finditer(r"const \[(\w+),\s*(set\w+)\]\s*=\s*useState", text):
            value, setter = m.group(1), m.group(2)
            if len(re.findall(rf"\b{setter}\b", text)) == 1:
                problems.append(f"{path.name}: {setter}() 호출 없음 -> {value}가 변하지 않음")
            elif len(re.findall(rf"\b{value}\b", text)) == 1:
                problems.append(f"{path.name}: {value}를 읽는 곳 없음 ({setter}만 호출)")
    return problems


def send_min_length() -> int | None:
    """전송 버튼이 열리는 최소 글자 수(workspace/constants.ts의 MIN_MESSAGE_LENGTH)."""
    path = SRC / "workspace" / "constants.ts"
    text = path.read_text("utf-8") if path.exists() else ""
    m = re.search(r"MIN_MESSAGE_LENGTH\s*=\s*(\d+)", text)
    return int(m.group(1)) if m else None


def inline_style_blocks() -> list[tuple[str, str]]:
    """(파일, style={{ ... }} 안의 내용) 목록. 템플릿 문자열 안의 }도 올바르게 처리한다."""
    found: list[tuple[str, str]] = []
    for path in source_files(".tsx"):
        text = path.read_text("utf-8")
        for m in re.finditer(r"style=\{\{", text):
            depth, i = 2, m.end()
            while i < len(text) and depth > 0:
                depth += (text[i] == "{") - (text[i] == "}")
                i += 1
            found.append((path.name, text[m.end(): i - 2]))
    return found


def inline_style_count() -> int:
    """JSX 인라인 style={{ ... }} 개수. 디자인 토큰·다크 모드와 어긋나기 쉬워 0으로 유지한다.

    예외(CSS로 표현할 수 없는, 실행 중에 계산되는 값):
    - 게이지 막대의 너비 `width: `${score}%``
    - 패널 너비를 CSS 변수로 넘기는 `"--aside-width"`, `"--rail-width"` 등(`"--`로 시작하는 키)
    """
    total = 0
    for _name, body in inline_style_blocks():
        if re.fullmatch(r"\s*width:\s*`\$\{[^}]+\}%`\s*", body):
            continue
        if re.search(r'"--[\w-]+"\s*:', body):
            continue
        total += 1
    return total


def login_guard_limits() -> tuple[int | None, int | None]:
    """프런트 loginGuard.ts의 (MAX_FAILURES, WINDOW_MINUTES)."""
    text = (SRC / "loginGuard.ts").read_text("utf-8") if (SRC / "loginGuard.ts").exists() else ""
    mf = re.search(r"MAX_FAILURES\s*=\s*(\d+)", text)
    wm = re.search(r"WINDOW_MINUTES\s*=\s*(\d+)", text)
    return (int(mf.group(1)) if mf else None, int(wm.group(1)) if wm else None)


# ------------------------------------------------------------------ CSS 구조 (styles/app/ 분할)
STYLES = SRC / "styles"


def css_import_problems() -> list[str]:
    """app.css는 styles/app/*.css를 @import 하는 목차다. 누락·중복·없는 파일은 화면 스타일 소실로 이어진다."""
    index = (STYLES / "app.css").read_text("utf-8")
    imported = re.findall(r"@import\s+['\"]\./app/([\w.-]+\.css)['\"]\s*;", _strip_comments(index))
    problems = [f"{n}: @import가 {imported.count(n)}번" for n in sorted(set(imported)) if imported.count(n) > 1]
    problems += [f"{n}: 파일 없음" for n in imported if not (STYLES / "app" / n).exists()]
    on_disk = {p.name for p in (STYLES / "app").glob("*.css")}
    problems += [f"{n}: app.css에서 import하지 않음" for n in sorted(on_disk - set(imported))]
    rules = re.sub(r"@import[^;]*;", "", _strip_comments(index)).strip()
    if rules:
        problems.append("app.css에 @import 외의 규칙이 있음 (목차로만 쓴다)")
    return problems


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _block(text: str, selector: str) -> str:
    """`selector {` 로 시작하는 최상위 블록의 본문(중괄호 균형)."""
    m = re.search(rf"(?m)^{re.escape(selector)}\s*\{{", text)
    if not m:
        return ""
    depth, i = 1, m.end()
    while i < len(text) and depth:
        depth += (text[i] == "{") - (text[i] == "}")
        i += 1
    return text[m.end() : i - 1]


def dark_mode_problems() -> list[str]:
    """다크 모드: tokens.css의 `.dark-mode`가 기존 토큰만 덮어쓰고, 모든 var(--x)가 정의돼 있어야 한다."""
    tokens = _strip_comments((STYLES / "tokens.css").read_text("utf-8"))
    root_vars = set(re.findall(r"(--[\w-]+)\s*:", _block(tokens, ":root")))
    dark_vars = set(re.findall(r"(--[\w-]+)\s*:", _block(tokens, ".dark-mode")))
    problems: list[str] = []
    if not root_vars:
        problems.append("tokens.css에 :root 토큰이 없음")
    if not dark_vars:
        problems.append("tokens.css에 .dark-mode 토큰 블록이 없음")
    if dark_vars - root_vars:
        problems.append(f".dark-mode에만 있는 토큰: {sorted(dark_vars - root_vars)}")
    declared = root_vars | dark_vars
    used: dict[str, set[str]] = {}
    for path in STYLES.rglob("*.css"):
        local = set(re.findall(r"(--[\w-]+)\s*:", _strip_comments(path.read_text("utf-8"))))
        for name in re.findall(r"var\(\s*(--[\w-]+)\s*[,)]", _strip_comments(path.read_text("utf-8"))):
            if name not in declared and name not in local:
                used.setdefault(name, set()).add(path.name)
    # 레이아웃 변수(--rail-width 등)는 TSX가 런타임에 설정한다
    runtime = set(re.findall(r"""['"`](--[\w-]+)['"`]""", "".join(p.read_text("utf-8") for p in source_files(".tsx"))))
    runtime |= set(re.findall(r"(--[\w-]+)\s*:", "".join(p.read_text("utf-8") for p in source_files(".tsx"))))
    for name, files in sorted(used.items()):
        if name not in runtime:
            problems.append(f"정의되지 않은 토큰 {name} ({', '.join(sorted(files))})")
    return problems


def print_problems() -> list[str]:
    """인쇄: @page와 @media print 규칙이 있고, 화면용 UI(타이틀바·레이아웃)를 숨겨야 한다."""
    text = _strip_comments((STYLES / "app" / "print.css").read_text("utf-8"))
    problems: list[str] = []
    if "@page" not in text:
        problems.append("print.css에 @page 없음")
    block = _block(text, "@media print")
    if not block:
        return problems + ["print.css에 @media print 없음"]
    hidden = re.search(r"\.titlebar[^{]*\{[^}]*display:\s*none", block) and re.search(r"\.layout[^{]*\{[^}]*display:\s*none", block)
    if not hidden:
        problems.append("@media print에서 .titlebar/.layout을 숨기지 않음")
    return problems
