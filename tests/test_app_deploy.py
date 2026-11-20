"""앱·배포 설정 및 유틸리티 테스트. 실행: python tests/test_app_deploy.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import utils  # noqa: E402


def test_resolve_secret_handles_placeholder_and_fallback():
    assert utils.resolve_secret({"GEMINI_API_KEY": "여기에_키"}, {}, "GEMINI_API_KEY") is None
    assert utils.resolve_secret({"GEMINI_API_KEY": "   "}, {"GEMINI_API_KEY": "env-key"}, "GEMINI_API_KEY") == "env-key"
    assert utils.resolve_secret({"GEMINI_API_KEY": "sec-key"}, {"GEMINI_API_KEY": "env-key"}, "GEMINI_API_KEY") == "sec-key"
    assert utils.resolve_secret(None, {}, "GEMINI_MODEL", "gemini-2.5-flash") == "gemini-2.5-flash"


def test_normalize_mime():
    assert utils.normalize_mime("image/jpg", "photo.jpg") == "image/jpeg"
    assert utils.normalize_mime("", "rack.webp") == "image/webp"
    assert utils.normalize_mime(None, "board.PNG") == "image/png"


def test_prepare_image_fallback_on_non_image_bytes():
    data, mime = utils.prepare_image(b"not-an-image", "", "photo.jpg")
    assert data == b"not-an-image"
    assert mime == "image/jpeg"


def test_sample_case_matches_knowledge_base():
    kb = json.loads((ROOT / "data" / "knowledge_base.json").read_text(encoding="utf-8"))
    sample = utils.load_sample_case(ROOT / "data" / "sample_case.json")
    assert sample["product_id"] in kb["products"]
    assert sample["industry"] in kb["industry_angles"]
    assert sample["install_type"] in kb["install_types"]
    assert all(tag in kb["problem_tags"] for tag in sample["problem_tags"])
    assert sample["notes"].strip()


def test_export_formatting():
    cards_text = utils.format_cards_text([{"no": 1, "headline": "제목", "text": "본문", "photo": "사진 1"}])
    assert "[1장] 제목" in cards_text
    md = utils.build_export_markdown("블로그 내용", cards_text)
    assert md.startswith("# 블로그") and "# 카드뉴스" in md


def test_llm_parse_json_strips_fences():
    try:
        import llm
    except ImportError:
        return  # google-genai 미설치 환경에서는 건너뜀
    parsed = llm._parse_json("```json\n{\"ok\": true}\n```")
    assert parsed == {"ok": True}


def test_resolve_secret_treats_example_placeholder_as_missing():
    assert utils.resolve_secret({"GEMINI_API_KEY": "PASTE_YOUR_KEY_HERE"}, {}, "GEMINI_API_KEY") is None


def test_photo_signature_changes_when_photos_change():
    a = [("a.jpg", b"one"), ("b.jpg", b"two")]
    assert utils.photo_signature([]) == ""
    assert utils.photo_signature(a) == utils.photo_signature(list(a))
    assert utils.photo_signature(a) != utils.photo_signature([("a.jpg", b"one")])  # 한 장 뺌
    assert utils.photo_signature(a) != utils.photo_signature([("a.jpg", b"one"), ("b.jpg", b"TWO")])  # 내용 바뀜
    assert utils.photo_signature(a) != utils.photo_signature([("c.jpg", b"one"), ("b.jpg", b"two")])  # 이름 바뀜


def test_error_hint_maps_common_failures():
    assert "GEMINI_API_KEY" in utils.error_hint(Exception("400 INVALID_ARGUMENT. API key not valid."))
    assert "1분" in utils.error_hint(Exception("429 RESOURCE_EXHAUSTED"))
    assert "GEMINI_MODEL" in utils.error_hint(Exception("404 NOT_FOUND. models/gemini-x is not found"))
    assert "다시 시도" in utils.error_hint(ValueError("모델이 빈 응답을 반환했습니다."))
    assert "다시 시도" in utils.error_hint(json.JSONDecodeError("bad", "{", 0))
    assert "팀에 공유" in utils.error_hint(RuntimeError("뭔가 이상함"))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
