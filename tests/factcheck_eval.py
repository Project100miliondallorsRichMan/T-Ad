"""생성 글 여러 건을 팩트체크에 돌려 검출 결과 표(마크다운)를 만든다. (#7)

사용법
  # 저장된 글만 검사 (API 키 불필요)
  python tests/factcheck_eval.py

  # Gemini로 세 업종 글을 새로 만들어 저장한 뒤 검사 (.streamlit/secrets.toml 또는 환경변수 GEMINI_API_KEY 필요)
  python tests/factcheck_eval.py --generate

글은 docs/factcheck_samples/*.json 에 저장된다. 형식은 앱의 생성 결과와 같다:
  {"meta": {...}, "blog": {"title", "body"}, "cards": [{"headline", "text"}, ...]}
표에서 '판정'은 사람이 근거와 대조해 채운다(오탐/미탐 기록용).
"""
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import factcheck as fc  # noqa: E402

KB = json.loads((ROOT / "data" / "knowledge_base.json").read_text(encoding="utf-8"))
SAMPLES = ROOT / "docs" / "factcheck_samples"

# 시연 사진(sample_photos/, tlinkcrm.com 설치 사례의 세 가지 설치 형태)에 맞춘 세 시나리오
SCENARIOS = [
    ("real_1_public", "ai_recording", "공공·복지", "스탠드형", ["단자함 공간 부족", "기존 전화기 유지 필요"],
     "사진 1: 사무실 창가 바닥에 세워 둔 검은색 녹취 서버 본체. 서버 랙 없이 단독으로 서 있다."),
    ("real_2_school", "school_recording", "교육(학교)", "미러링 스위치허브", ["기존 전화기 유지 필요"],
     "사진 1: 책상 위 공유기 옆에 손바닥만 한 미러링 스위치 허브. 책상 아래 단자함에 케이블이 모여 있다."),
    ("real_3_callcenter", "ai_recording", "콜센터·기업", "랙거치형", ["서버랙 공간 부족", "다수 회선 동시 녹취"],
     "사진 1: 기존 서버 랙 두 곳에 1U 녹취 서버가 장착됨. 스위치·패치패널과 같은 랙에 있다."),
]


def secret(name, default=None):
    path = ROOT / ".streamlit" / "secrets.toml"
    if path.exists():
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        if data.get(name):
            return data[name]
    return os.environ.get(name, default)


def generate():
    import llm

    key, model = secret("GEMINI_API_KEY"), secret("GEMINI_MODEL", "gemini-2.5-flash")
    if not key or not key.isascii():
        sys.exit("GEMINI_API_KEY가 없습니다. .streamlit/secrets.toml에 넣어 주세요.")
    SAMPLES.mkdir(parents=True, exist_ok=True)
    for name, pid, industry, itype, tags, notes in SCENARIOS:
        out = llm.generate_content(key, model, KB, pid, industry, itype, tags, notes)
        out["meta"] = {"product": pid, "industry": industry, "notes": notes, "model": model, "source": "gemini"}
        (SAMPLES / f"{name}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print("generated", name)


def texts(doc):
    yield "블로그 제목", doc["blog"]["title"]
    yield "블로그 본문", doc["blog"]["body"]
    for c in doc.get("cards", []):
        yield f"카드 {c.get('no', '')}", f"{c.get('headline', '')}\n{c.get('text', '')}"


def evaluate():
    files = sorted(SAMPLES.glob("*.json"))
    if not files:
        sys.exit("검사할 글이 없습니다. --generate로 먼저 만드세요.")
    rows, summary = [], []
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        meta = doc["meta"]
        allowed = fc.build_allowed(fc.sources_from_kb(KB, meta["product"]) + [(meta.get("notes", ""), "현장 확인(직원)")])
        n = {"ok": 0, "unverified": 0, "banned": 0}
        for where, text in texts(doc):
            for x in fc.check(text, allowed, KB["banned_phrases"]):
                n[x.status] += 1
                ctx = text[max(0, x.start - 12):x.end + 12].replace("\n", " ")
                rows.append(f"| {f.stem} | {where} | `{x.text}` | {x.status} | …{ctx}… | |")
        summary.append(f"| {f.stem} | {meta.get('source', '')} | {meta['industry']} | {n['ok']} | {n['unverified']} | {n['banned']} |")
    print("| 글 | 출처 | 업종 | 근거 있음 | 확인 필요 | 금지 표현 |\n|---|---|---|---|---|---|")
    print("\n".join(summary))
    print("\n| 글 | 위치 | 검출 | 결과 | 문맥 | 판정(사람) |\n|---|---|---|---|---|---|")
    print("\n".join(rows))


if __name__ == "__main__":
    if "--generate" in sys.argv:
        generate()
    evaluate()
