import re


PATTERNS = [
    (re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}"), "[전화번호]"),
    (re.compile(r"\b\d{6}[-\s]?[1-4]\d{6}\b"), "[주민등록번호]"),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[이메일]"),
]


def mask_pii(text: str) -> str:
    result = text
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result

