"""생성된 글의 수치·금지 표현을 제품 근거와 대조한다. AI가 아니라 규칙으로 검증한다."""
import re
from dataclasses import dataclass
from html import escape

# shortcut: 단위가 붙은 숫자만 검사한다(형식용 숫자 오탐 방지). 단위 없는 숫자 주장은 놓친다 — 필요하면 단위 목록을 늘린다.
# 값은 정규화된 단위. 표기가 달라도 같은 뜻이면 같은 값으로 묶는다('곳'='개', '프로'='%'). 긴 단위부터 맞춘다.
_UNITS = {
    # '개국'(나라 수)은 '언어'와 다른 값이다. 홈페이지 표기 '30개국'을 '30개 언어'로 바꿔 쓰면 '확인 필요'.
    "개 언어": "언어", "개언어": "언어", "개국어": "언어", "개국": "개국",
    "퍼센트": "%", "%": "%", "프로": "%",
    "개월": "개월", "시간": "시간", "회선": "회선",
    "석": "석", "원": "원", "개": "개", "곳": "개", "건": "건", "배": "배",
    "명": "명", "분": "분", "초": "초", "년": "년", "호": "호", "대": "대", "일": "일",
}
# 단위 뒤에 오면 단위가 아닌 경우: '3프로그램', '2프로젝트'
_UNIT_GUARD = {"프로": "(?![그젝세필모])"}
_UNIT_ALT = "|".join(
    re.escape(u) + _UNIT_GUARD.get(u, "") for u in sorted(_UNITS, key=len, reverse=True)
)
_MULT = {"천": 1_000, "만": 10_000, "억": 100_000_000}
_DIGITS = r"(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?"
_NUM_RE = re.compile(
    r"(?<![\d.,])" + _DIGITS + r"\s*([천만억])?\s*(?:여\s*)?(" + _UNIT_ALT + ")"
)
# '₩1,500,000'처럼 단위가 앞에 오는 금액
_WON_RE = re.compile(r"₩\s*" + _DIGITS + r"(?![\d,])")
# '두 배', '서른 개 언어', '하루'처럼 한글로 쓴 수. 앞이 한글이면 낱말 일부('부가세 배')라 건너뛴다.
# '대'는 '세대'·'네 대'가 헷갈려 뺀다.
_NATIVE = {
    "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9,
    "열": 10, "스무": 20, "스물": 20, "서른": 30, "마흔": 40, "쉰": 50,
}
_NATIVE_UNITS = ["개국", "개 언어", "개국어", "배", "개", "곳", "명", "시간", "회선"]
_NATIVE_RE = re.compile(
    r"(?<![가-힣])("
    + "|".join(sorted(_NATIVE, key=len, reverse=True))
    + r")\s*(?:여\s*)?("
    + "|".join(re.escape(u) for u in sorted(_NATIVE_UNITS, key=len, reverse=True))
    + ")"
)
_DAYS_RE = re.compile(r"(?<![가-힣])(하루|이틀|사흘|나흘)")
_DAYS = {"하루": 1, "이틀": 2, "사흘": 3, "나흘": 4}

# 금지어가 들어 있지만 광고 주장이 아닌 낱말. 이 안에 든 금지어는 건너뛴다.
BANNED_EXCEPTIONS = ["최고경영자", "최고기술책임자", "최고정보보호책임자", "최고책임자", "보장성", "1등급"]


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


def _numbers(text: str):
    """(start, end, 원문, 정규화 키)를 모두 낸다."""
    for m in _NUM_RE.finditer(text):
        yield m.start(), m.end(), m.group(0), _key(m)
    for m in _WON_RE.finditer(text):
        num = float(m.group(1).replace(",", "") + (m.group(2) or ""))
        yield m.start(), m.end(), m.group(0), (round(num, 6), "원")
    for m in _NATIVE_RE.finditer(text):
        yield m.start(), m.end(), m.group(0), (float(_NATIVE[m.group(1)]), _UNITS[m.group(2)])
    for m in _DAYS_RE.finditer(text):
        yield m.start(), m.end(), m.group(0), (float(_DAYS[m.group(1)]), "일")


def sources_from_kb(kb: dict, product_id: str) -> list[tuple[str, str]]:
    """선택한 제품과 회사 공통 근거만 허용 근거로 쓴다."""
    p = kb["products"][product_id]
    return [(c["text"], f'{p["name"]} · {c["source"]}') for c in p["claims"]] + [
        (c["text"], f'회사 · {c["source"]}') for c in kb["company"]["claims"]
    ]


def build_allowed(sources: list[tuple[str, str]]) -> dict[tuple, str]:
    allowed: dict[tuple, str] = {}
    for text, label in sources:
        for *_, k in _numbers(text):
            allowed.setdefault(k, label)
    return allowed


def check(text: str, allowed: dict[tuple, str], banned: list[str],
          exceptions: list[str] = BANNED_EXCEPTIONS) -> list[Finding]:
    found = []
    for start, end, raw, k in _numbers(text):
        if k == (100.0, "%"):  # '100 %', '100퍼센트'도 '100%'와 같은 단정 표현
            found.append(Finding(start, end, raw, "banned"))
        else:
            found.append(Finding(start, end, raw, "ok" if k in allowed else "unverified", allowed.get(k, "")))
    safe = [(m.start(), m.end()) for w in exceptions for m in re.finditer(re.escape(w), text)]
    for phrase in banned:
        for m in re.finditer(re.escape(phrase), text):
            if any(s <= m.start() and m.end() <= e for s, e in safe):
                continue
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
