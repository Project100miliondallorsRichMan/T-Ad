"""T-Ad: 설치 사진 → 분석 → 근거 매칭 → 생성 → 검수"""
import json
import os
from pathlib import Path

import streamlit as st

import factcheck
import llm
import ui

KB = json.loads((Path(__file__).parent / "data" / "knowledge_base.json").read_text(encoding="utf-8"))


def secret(name: str, default: str | None = None) -> str | None:
    try:
        return st.secrets[name]
    except Exception:  # secrets.toml이 없으면 환경변수로
        return os.environ.get(name, default)


API_KEY = secret("GEMINI_API_KEY")
MODEL = secret("GEMINI_MODEL", "gemini-2.5-flash")

st.set_page_config(page_title="T-Ad", layout="wide")
st.title("T-Ad")
st.caption("설치 사진을 기술의 증거로 · 사진 → 분석 → 근거 매칭 → 생성 → 직원 검수")

if not API_KEY or API_KEY == "PASTE_YOUR_KEY_HERE":
    st.error("GEMINI_API_KEY가 없습니다. .streamlit/secrets.toml 또는 환경변수에 넣어 주세요.")
    st.stop()

st.markdown(ui.CSS, unsafe_allow_html=True)
stage = 4 if st.session_state.get("content") else 2 if st.session_state.get("analysis") else 1
st.markdown(ui.steps_html(stage), unsafe_allow_html=True)

with st.sidebar:
    product_id = st.selectbox("제품", list(KB["products"]), format_func=lambda k: KB["products"][k]["name"])
    industry = st.selectbox("업종", list(KB["industry_angles"]))
    st.caption(f"이 업종의 관심사: {KB['industry_angles'][industry]}")

# 1. 사진 업로드
st.header("1. 사진 업로드")
checked = st.checkbox("사진 속 IP 스티커·내선번호·패치패널 라벨·얼굴·간판이 가려졌거나 없음을 확인했습니다.")
files = st.file_uploader(
    "설치 전·후 사진", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=True, disabled=not checked
)
if files:
    cols = st.columns(min(len(files), 4))
    for i, f in enumerate(files):
        cols[i % len(cols)].image(f, caption=f"사진 {i + 1}")

    if st.button("사진 분석", type="primary"):
        with st.spinner("사진을 읽는 중..."):
            try:
                st.session_state.analysis = llm.analyze_photos(
                    API_KEY, MODEL, [(f.getvalue(), f.type) for f in files], KB
                )
                st.session_state.thumbs = [ui.thumb_b64(f.getvalue()) for f in files]  # 카드 미리보기 배경
                st.session_state.pop("content", None)
                st.rerun()  # 단계 표시를 바로 갱신
            except Exception as e:
                st.error(f"사진 분석 실패: {e}")

# 2. 직원 확인
a = st.session_state.get("analysis")
if a:
    st.header("2. 태그 확인 (직원)")
    cands = [t for t in a.get("install_type_candidates", []) if t in KB["install_types"]]
    install_type = st.selectbox(
        "설치 형태", KB["install_types"], index=KB["install_types"].index(cands[0]) if cands else 0
    )
    tags = st.multiselect(
        "문제 태그", KB["problem_tags"],
        default=[t for t in a.get("problem_tag_candidates", []) if t in KB["problem_tags"]],
    )
    notes = st.text_area(
        "사진 설명 — 틀린 부분은 고쳐 주세요. 여기 적은 수치는 '현장 확인' 근거로 인정됩니다.",
        "\n".join(f"사진 {p.get('index')}: {p.get('description', '')}" for p in a.get("photos", [])),
        height=140,
    )
    if a.get("uncertain"):
        st.info("AI가 확신하지 못한 점: " + " / ".join(a["uncertain"]))

    if st.button("콘텐츠 생성", type="primary"):
        with st.spinner("근거를 맞춰 글을 쓰는 중..."):
            try:
                st.session_state.content = llm.generate_content(
                    API_KEY, MODEL, KB, product_id, industry, install_type, tags, notes
                )
                st.session_state.notes = notes
                for k in ("blog_edit", "cards_edit"):  # 새로 생성하면 이전 수정본을 버린다
                    st.session_state.pop(k, None)
                st.rerun()
            except Exception as e:
                st.error(f"생성 실패: {e}")

# 3. 검수
c = st.session_state.get("content")
if c:
    st.header("3. 검수 · 코드 팩트체크")
    badge = st.empty()  # 아래 글을 검사한 뒤 맨 위에 결과를 채운다
    allowed = factcheck.build_allowed(
        factcheck.sources_from_kb(KB, product_id) + [(st.session_state.get("notes", ""), "현장 확인(직원)")]
    )
    left, right = st.columns(2)
    blog = left.text_area(
        "블로그 글 (수정하면 검사가 바로 다시 돌아갑니다)",
        f"{c['blog']['title']}\n\n{c['blog']['body']}", height=300, key="blog_edit",
    )
    cards = right.text_area(
        "카드뉴스 5장 문구",
        "\n\n".join(f"[{x.get('no')}장] {x.get('headline', '')}\n{x.get('text', '')}\n(사진: {x.get('photo', '')})"
                    for x in c.get("cards", [])),
        height=300, key="cards_edit",
    )
    results = [(label, text, factcheck.check(text, allowed, KB["banned_phrases"]))
               for label, text in (("블로그", blog), ("카드뉴스", cards))]
    bad = sum(f.status != "ok" for _, _, found in results for f in found)
    total = sum(len(found) for _, _, found in results)
    badge.markdown(ui.badge_html(bad, total - bad), unsafe_allow_html=True)

    st.subheader("카드뉴스 미리보기")
    st.markdown(
        ui.cards_html(ui.parse_cards(cards), st.session_state.get("thumbs", []), allowed, KB["banned_phrases"]),
        unsafe_allow_html=True,
    )
    for label, text, found in results:
        n = sum(f.status != "ok" for f in found)
        st.subheader(f"{label}: 확인 필요 {n}건 · 근거 확인 {len(found) - n}건")
        st.markdown(factcheck.highlight(text, found), unsafe_allow_html=True)

    if c.get("used_claims"):
        st.caption("AI가 사용했다고 밝힌 근거: " + ", ".join(c["used_claims"]))
    st.download_button(
        "검수본 내려받기 (.md)", f"# 블로그\n\n{blog}\n\n# 카드뉴스\n\n{cards}\n",
        file_name="t-ad_content.md",
    )
