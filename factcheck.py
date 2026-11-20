"""생성된 글의 수치·금지 표현을 제품 근거와 대조한다. AI가 아니라 규칙으로 검증한다."""
import re
from dataclasses import dataclass
from html import escape

# 긴 단위를 먼저 둬야 '개 언어'가 '개'보다 먼저 잡힌다.
# shortcut: 단위가 붙은 숫자만 검사한다(형식용 숫자 오탐 방지). 단위 없는 숫자 주장은 놓친다 — 필요하면 단위 목록을 늘린다.
_UNITS = {
    "개 언어": "언어", "개언어": "언어", "개국어": "언어", "개국": "개국", "퍼센트": "%", "개월": "개월", "시간": "시간",
    "%": "%", "석": "석", "원": "원", "개": "개", "곳": "곳", "건": "건", "배": "배",
    "명": "명", "분": "분", "초": "초", "년": "년", "호": "호", "대": "대", "일": "일",
}
_MULT = {"천": 1_000, "만": 10_000, "억": 100_000_000}
_NUM_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\s*([천만억])?\s*(?:여\s*)?("
    + "|".join(re.escape(u) for u in _UNITS)
    + ")"
)


@dataclass
class Finding:
    start: int
    end: int
    text: str
    status: str  # "ok" | "unverified" | "banned"
    source: str = ""


def _key(m: re.Match) -> tuple:
    """'3,000석'과 '3000석', '150만 원'과 '1,500,000원'이 같은 값이 되도록 정규화."""
    num = float(m.group(1).replace(",", "") + (m.group(2) or ""))
    num *= _MULT.get(m.group(3), 1)
    return (round(num, 6), _UNITS[m.group(4)])


def sources_from_kb(kb: dict, product_id: str) -> list[tuple[str, str]]:
    """선택한 제품과 회사 공통 근거만 허용 근거로 쓴다."""
    p = kb["products"][product_id]
    return [(c["text"], f'{p["name"]} · {c["source"]}') for c in p["claims"]] + [
        (c["text"], f'회사 · {c["source"]}') for c in kb["company"]["claims"]
    ]


def build_allowed(sources: list[tuple[str, str]]) -> dict[tuple, str]:
    allowed: dict[tuple, str] = {}
    for text, label in sources:
        for m in _NUM_RE.finditer(text):
            allowed.setdefault(_key(m), label)
    return allowed


def check(text: str, allowed: dict[tuple, str], banned: list[str]) -> list[Finding]:
    found = []
    for m in _NUM_RE.finditer(text):
        k = _key(m)
        found.append(Finding(m.start(), m.end(), m.group(0), "ok" if k in allowed else "unverified", allowed.get(k, "")))
    for phrase in banned:
        for m in re.finditer(re.escape(phrase), text):
            found.append(Finding(m.start(), m.end(), phrase, "banned"))
    # 겹치면 금지 표현, 그다음 긴 것을 우선한다(예: '100%', '업계 최고' vs '최고').
    found.sort(key=lambda f: (f.start, f.status != "banned", f.start - f.end))
    result, last_end = [], -1
    for f in found:
        if f.start >= last_end:
            result.append(f)
            last_end = f.end
    return result


_STYLE = {
    "ok": ("#e3f4e8", "#1b5e20", "근거"),
    "unverified": ("#fde2e1", "#b71c1c", "확인 필요"),
    "banned": ("#fde2e1", "#b71c1c", "금지 표현"),
}


def highlight(text: str, findings: list[Finding]) -> str:
    """검사 결과를 색으로 표시한 HTML. 원문은 escape해서 넣는다."""
    out, pos = [], 0
    for f in findings:
        bg, fg, label = _STYLE[f.status]
        tip = escape(f.source or label, quote=True)
        out.append(escape(text[pos:f.start]))
        out.append(
            f'<span title="{tip}" style="background:{bg};color:{fg};font-weight:600;'
            f'padding:0 2px;border-radius:3px">{escape(f.text)}<sup>{label}</sup></span>'
        )
        pos = f.end
    out.append(escape(text[pos:]))
    # 한 줄짜리 div로 감싸야 Streamlit markdown이 본문을 마크다운으로 해석하지 않는다.
    return '<div style="line-height:1.9">' + "".join(out).replace("\n", "<br>") + "</div>"
