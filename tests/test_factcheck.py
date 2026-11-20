"""팩트체크 테스트. 실행: python -m pytest  또는  python tests/test_factcheck.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import factcheck as fc  # noqa: E402

KB = json.loads((ROOT / "data" / "knowledge_base.json").read_text(encoding="utf-8"))
BANNED = KB["banned_phrases"]


def run(text, product="ai_recording", extra=()):
    allowed = fc.build_allowed(fc.sources_from_kb(KB, product) + list(extra))
    return [(f.text, f.status) for f in fc.check(text, allowed, BANNED)]


# 테스트 데이터 1: 지식 베이스에 있는 수치는 통과
def test_kb_number_passes():
    assert run("기존 전화기 그대로, 녹취 성공률 99%(회사 발표)입니다.") == [("99%", "ok")]


# 테스트 데이터 2: AI가 지어낸 수치는 '확인 필요'
def test_invented_numbers_flagged():
    assert run("도입 후 민원 30% 감소, 설치는 2시간이면 끝납니다.") == [
        ("30%", "unverified"),
        ("2시간", "unverified"),
    ]


# 테스트 데이터 3: 금지 표현 검출 + 표기가 달라도 같은 수치로 인정
def test_banned_and_normalized():
    assert run("업계 최고 수준! 최대 3000석까지 구축했습니다.") == [
        ("업계 최고", "banned"),
        ("3000석", "ok"),
    ]


def test_man_won_and_yeo_normalized():
    assert run("1회 150만원, 150개 학교가 씁니다.", product="school_recording") == [
        ("150만원", "ok"),
        ("150개", "ok"),
    ]


def test_other_product_numbers_not_allowed():
    # 학교용 가격은 AI 녹취 글의 근거가 될 수 없다
    assert run("150만 원이면 됩니다.") == [("150만 원", "unverified")]


def test_staff_confirmed_note_is_a_source():
    note = [("사진 2: 전화기 12대가 보임", "현장 확인(직원)")]
    assert run("전화기 12대를 그대로 썼습니다.", extra=note) == [("12대", "ok")]


def test_format_numbers_ignored():
    assert run("[1장] 카드뉴스 5장 구성, 사진 3") == []


def test_highlight_escapes_html():
    html = fc.highlight("<b>99%</b>", fc.check("<b>99%</b>", {}, BANNED))
    assert "<b>" not in html and "&lt;b&gt;" in html and "확인 필요" in html


# 홈페이지 표기 '30개국'은 통과, 나라 수를 언어 수로 바꿔 쓴 '30개 언어'는 '확인 필요'
def test_countries_not_languages():
    assert run("30개국 이상 실시간 통역", product="tlink_on") == [("30개국", "ok")]
    assert run("30개 언어 실시간 통역", product="tlink_on") == [("30개 언어", "unverified")]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
