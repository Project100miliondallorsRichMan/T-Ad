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


def _parse_json(raw: str | None) -> dict:
    if not raw or not raw.strip():
        raise ValueError("모델이 빈 응답을 반환했습니다.")
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


def _ask_json(api_key: str, model: str, contents: list) -> dict:
    # 클라이언트를 변수로 잡아 둬야 요청 전에 닫히지 않는다(google-genai 3.x).
    with genai.Client(api_key=api_key) as client:
        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.4),
        )
    return _parse_json(getattr(resp, "text", None))


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
