"""Gemini 호출. 프롬프트 원문은 prompts/ 폴더에 있다."""
import json
from pathlib import Path

from google import genai
from google.genai import types

PROMPTS = Path(__file__).parent / "prompts"


def _render(name: str, **values: str) -> str:
    # str.format 대신 replace: 프롬프트 안 JSON 예시의 중괄호를 건드리지 않기 위해
    text = (PROMPTS / name).read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{" + k + "}", v)
    return text


def _ask_json(api_key: str, model: str, contents: list) -> dict:
    # 클라이언트를 변수로 잡아 둬야 요청 전에 닫히지 않는다(google-genai 3.x).
    # 시간 제한·재시도 1회: 기본값은 429/5xx에서 끝없이 재시도해 화면이 멈춘 것처럼 보인다.
    opts = types.HttpOptions(timeout=90_000, retry_options=types.HttpRetryOptions(attempts=2))
    with genai.Client(api_key=api_key, http_options=opts) as client:
        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4),
        )
    return json.loads(resp.text)


def friendly_error(e: Exception) -> str:
    """시연 중에도 다음 행동을 알 수 있게 API 오류를 한국어 안내로 바꾼다."""
    msg = str(e)
    if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
        return "API 사용량 한도를 넘었습니다. 다른 API 키를 쓰거나 한도가 풀린 뒤 다시 시도하세요. (" + msg[:120] + ")"
    if any(s in msg for s in ("UNAVAILABLE", "DEADLINE_EXCEEDED", "503", "504", "timed out", "Timeout")):
        return "AI 서버가 바쁘거나 응답이 늦습니다. 잠시 후 다시 눌러 주세요."
    if "API key not valid" in msg or "PERMISSION_DENIED" in msg:
        return "API 키가 올바르지 않습니다. .streamlit/secrets.toml의 GEMINI_API_KEY를 확인하세요."
    if "NOT_FOUND" in msg:
        return "모델을 찾을 수 없습니다. secrets의 GEMINI_MODEL을 확인하세요. (" + msg[:120] + ")"
    return msg


def analyze_photos(api_key: str, model: str, images: list[tuple[bytes, str]], kb: dict) -> dict:
    prompt = _render(
        "analyze_photo.md",
        install_types=", ".join(kb["install_types"]),
        problem_tags=", ".join(kb["problem_tags"]),
    )
    parts = [types.Part.from_bytes(data=b, mime_type=m) for b, m in images]
    return _ask_json(api_key, model, parts + [prompt])


def generate_content(api_key: str, model: str, kb: dict, product_id: str, industry: str,
                     install_type: str, tags: list[str], notes: str) -> dict:
    p = kb["products"][product_id]
    claims = "\n".join(
        f"- [{c['id']}] {c['text']}" + (f" ({c['note']})" if c.get("note") else "")
        for c in p["claims"] + kb["company"]["claims"]
    )
    prompt = _render(
        "generate_content.md",
        product=p["name"],
        industry=industry,
        industry_angle=kb["industry_angles"][industry],
        install_type=install_type,
        problem_tags=", ".join(tags) or "없음",
        photo_notes=notes or "없음",
        claims=claims,
    )
    return _ask_json(api_key, model, [prompt])
