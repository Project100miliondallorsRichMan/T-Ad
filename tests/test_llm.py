"""API 오류 안내 테스트. 실행: python tests/test_llm.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import llm  # noqa: E402


def test_friendly_error_messages():
    f = lambda s: llm.friendly_error(Exception(s))  # noqa: E731
    assert f("429 RESOURCE_EXHAUSTED. quota").startswith("API 사용량 한도")
    assert f("504 DEADLINE_EXCEEDED").startswith("AI 서버가 바쁘거나")
    assert f("503 UNAVAILABLE").startswith("AI 서버가 바쁘거나")
    assert f("400 API key not valid").startswith("API 키가 올바르지")
    assert f("404 NOT_FOUND model").startswith("모델을 찾을 수 없습니다")
    assert f("something else") == "something else"


if __name__ == "__main__":
    test_friendly_error_messages()
    print("ok test_friendly_error_messages")
