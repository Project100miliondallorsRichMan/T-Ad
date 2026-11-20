"""시연 화면 조각 테스트. 실행: python tests/test_ui.py"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image  # noqa: E402

import ui  # noqa: E402


def test_parse_cards_roundtrip():
    text = "[1장] 단자함 꽉 찼다고요?\n벽에 겁니다\n(사진: 1)\n\n[2장] 전화기는 그대로\n교체 없음\n두 줄째\n(사진: 사진 3)"
    assert ui.parse_cards(text) == [
        {"no": 1, "headline": "단자함 꽉 찼다고요?", "text": "벽에 겁니다", "photo": "1"},
        {"no": 2, "headline": "전화기는 그대로", "text": "교체 없음 두 줄째", "photo": "사진 3"},
    ]


def test_parse_cards_tolerates_hand_edits():
    # 직원이 머리표나 사진 줄을 지워도 깨지지 않는다
    assert ui.parse_cards("제목만\n본문\n\n\n[3장] 셋째") == [
        {"no": 1, "headline": "제목만", "text": "본문", "photo": ""},
        {"no": 3, "headline": "셋째", "text": "", "photo": ""},
    ]


def test_cards_html_picks_photo_and_marks_claims():
    cards = [{"no": 1, "headline": "민원 30% 감소", "text": "", "photo": "2"}]
    html = ui.cards_html(cards, ["AAA", "BBB"], {}, [])
    assert "base64,BBB" in html and "확인 필요" in html


def test_steps_and_badge():
    s = ui.steps_html(3)
    assert s.count('class="tad-step done"') == 2 and s.count('class="tad-step active"') == 1
    assert "확인 필요 0건" in ui.badge_html(0, 4) and "확인 필요 2건" in ui.badge_html(2, 1)


def test_thumb_respects_size():
    buf = io.BytesIO()
    Image.new("RGB", (2000, 1000), "gray").save(buf, "PNG")
    out = Image.open(io.BytesIO(__import__("base64").b64decode(ui.thumb_b64(buf.getvalue()))))
    assert max(out.size) == 640


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
