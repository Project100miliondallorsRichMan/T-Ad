"""T-Ad: 설치 사진 → 분석 → 근거 매칭 → 생성 → 검수"""
import json
import os
from pathlib import Path

import streamlit as st

import factcheck
import llm
import ui
import utils

ROOT = Path(__file__).parent
KB = json.loads((ROOT / "data" / "knowledge_base.json").read_text(encoding="utf-8"))
SAMPLE_CASE_PATH = ROOT / "data" / "sample_case.json"

# 사진·사례가 바뀌면 함께 지워야 하는 결과들
RESULT_KEYS = ("analysis", "content", "generated_meta", "notes", "blog_edit", "cards_edit", "thumbs")

st.set_page_config(page_title="T-Ad", layout="wide")


def _get_secret(name: str, default: str | None = None) -> str | None:
    try:
        secrets_obj = st.secrets
    except Exception:
        secrets_obj = None
    return utils.resolve_secret(secrets_obj, os.environ, name, default)


def _clear_results() -> None:
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)


def _load_sample_case() -> None:
    sample = utils.load_sample_case(SAMPLE_CASE_PATH)
    _clear_results()
    st.session_state["product_id"] = sample["product_id"]
    st.session_state["industry"] = sample["industry"]
    st.session_state["analysis"] = {
        "photos": [{"index": 1, "description": sample["notes"]}],
        "install_type_candidates": [sample["install_type"]],
        "problem_tag_candidates": sample["problem_tags"],
        "uncertain": sample.get("uncertain", []),
        "_sample_title": sample.get("title", "대표 설치 사례"),
        "_raw_notes": sample["notes"],
    }
    # 지금 올라와 있는 사진 기준으로 묶어 둬야, 다음 실행에서 '사진 바뀜'으로 지워지지 않는다
    st.session_state["analysis_sig"] = st.session_state.get("photo_sig", "")
    st.session_state["analysis_seq"] = st.session_state.get("analysis_seq", 0) + 1


def _show_failure(what: str, retry_label: str, exc: Exception) -> None:
    st.error(f"{what} 실패: {exc}")
    st.info(f"{utils.error_hint(exc)} 준비되면 **{retry_label}** 버튼을 다시 눌러 주세요.")


def _run_generate(api_key: str, model: str, product_id: str, industry: str,
                  install_type: str, tags: list[str], notes: str, retry_label: str) -> None:
    with st.spinner("근거를 맞춰 글을 쓰는 중..."):
        try:
            st.session_state.content = llm.generate_content(
                api_key, model, KB, product_id, industry, install_type, tags, notes
            )
            st.session_state.generated_meta = (product_id, industry)
            st.session_state.notes = notes
            for k in ("blog_edit", "cards_edit"):  # 새로 생성하면 이전 수정본을 버린다
                st.session_state.pop(k, None)
        except Exception as e:
            _show_failure("콘텐츠 생성", retry_label, e)


API_KEY = _get_secret("GEMINI_API_KEY")
MODEL = _get_secret("GEMINI_MODEL", "gemini-2.5-flash") or "gemini-2.5-flash"

st.title("T-Ad")
st.caption("설치 사진을 기술의 증거로 · 사진 → 분석 → 근거 매칭 → 생성 → 직원 검수")

if not API_KEY:
    st.error("GEMINI_API_KEY가 설정되지 않았습니다.")
    st.markdown(
        """
**배포/실행 환경에 따라 아래 중 한 곳에 키를 설정해 주세요.**
- **Streamlit Community Cloud**: `App settings` → `Secrets`에 아래 내용 입력
- **로컬 실행**: `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사 후 입력
        """
    )
    st.code('GEMINI_API_KEY = "AIza..."\nGEMINI_MODEL = "gemini-2.5-flash"', language="toml")
    st.stop()

st.markdown(ui.CSS, unsafe_allow_html=True)
steps_slot = st.empty()  # 단계 표시는 이번 실행의 결과가 정해진 뒤 맨 끝에서 채운다

product_ids = list(KB["products"])
industries = list(KB["industry_angles"])

with st.sidebar:
    product_id = st.selectbox(
        "제품",
        product_ids,
        format_func=lambda k: KB["products"][k]["name"],
        key="product_id",
    )
    industry = st.selectbox("업종", industries, key="industry")
    st.caption(f"이 업종의 관심사: {KB['industry_angles'][industry]}")

    st.divider()
    if SAMPLE_CASE_PATH.exists():
        st.button("대표 설치 사례 불러오기", on_click=_load_sample_case, use_container_width=True)
    st.button("작업 초기화", on_click=_clear_results, use_container_width=True)
    st.caption(f"모델: `{MODEL}` · 등록 제품 {len(product_ids)}종")

# 1. 사진 업로드
st.header("1. 사진 업로드")
checked = st.checkbox("사진 속 IP 스티커·내선번호·패치패널 라벨·얼굴·간판이 가려졌거나 없음을 확인했습니다.")
if not checked:
    st.info("위 보안·개인정보 노출 확인 항목을 체크하면 사진 업로드가 활성화됩니다. (사진 없이 시험하려면 왼쪽 '대표 설치 사례 불러오기'를 누르세요.)")

files = st.file_uploader(
    "설치 전·후 사진",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
    disabled=not checked,
)
photo_sig = utils.photo_signature([(f.name, f.getvalue()) for f in files or []])
st.session_state["photo_sig"] = photo_sig

# 분석에 쓴 사진과 지금 올라온 사진이 다르면 이전 분석·생성 결과를 버린다
if st.session_state.get("analysis") and st.session_state.get("analysis_sig", "") != photo_sig:
    _clear_results()
    st.info("사진이 바뀌어 이전 분석·생성 결과를 지웠습니다. 새 사진으로 다시 분석해 주세요.")

prepared_images: list[tuple[bytes, str]] = []
if files:
    cols = st.columns(min(len(files), 4))
    for i, f in enumerate(files):
        img_bytes, img_mime = utils.prepare_image(f.getvalue(), f.type, f.name)
        prepared_images.append((img_bytes, img_mime))
        cols[i % len(cols)].image(img_bytes, caption=f"사진 {i + 1}")

    if st.button("사진 분석", type="primary"):
        with st.spinner("사진을 읽는 중..."):
            try:
                analysis = llm.analyze_photos(API_KEY, MODEL, prepared_images, KB)
                _clear_results()
                st.session_state.analysis = analysis
                st.session_state.analysis_sig = photo_sig
                st.session_state.thumbs = [ui.thumb_b64(b) for b, _ in prepared_images]  # 카드 미리보기 배경
                st.session_state["analysis_seq"] = st.session_state.get("analysis_seq", 0) + 1
            except Exception as e:
                _show_failure("사진 분석", "사진 분석", e)

# 2. 직원 확인
a = st.session_state.get("analysis")
if a:
    st.header("2. 태그 확인 (직원)")
    if a.get("_sample_title"):
        st.info(f"불러온 사례: {a['_sample_title']}")

    seq = st.session_state.get("analysis_seq", 0)
    cands = [t for t in a.get("install_type_candidates", []) if t in KB["install_types"]]
    install_type = st.selectbox(
        "설치 형태",
        KB["install_types"],
        index=KB["install_types"].index(cands[0]) if cands else 0,
        key=f"install_type_{seq}",
    )
    tags = st.multiselect(
        "문제 태그",
        KB["problem_tags"],
        default=[t for t in a.get("problem_tag_candidates", []) if t in KB["problem_tags"]],
        key=f"problem_tags_{seq}",
    )
    default_notes = a.get("_raw_notes") or "\n".join(
        f"사진 {p.get('index')}: {p.get('description', '')}" for p in a.get("photos", [])
    )
    notes = st.text_area(
        "사진 설명 — 틀린 부분은 고쳐 주세요. 여기 적은 수치는 '현장 확인' 근거로 인정됩니다.",
        default_notes,
        height=140,
        key=f"notes_{seq}",
    )
    if a.get("uncertain"):
        st.info("AI가 확신하지 못한 점: " + " / ".join(a["uncertain"]))

    if st.button("콘텐츠 생성", type="primary"):
        _run_generate(API_KEY, MODEL, product_id, industry, install_type, tags, notes, "콘텐츠 생성")

# 3. 검수
c = st.session_state.get("content")
if c:
    st.header("3. 검수 · 코드 팩트체크")
    badge = st.empty()  # 아래 글을 검사한 뒤 맨 위에 결과를 채운다
    gen_meta = st.session_state.get("generated_meta")
    if gen_meta and gen_meta != (product_id, industry) and a:
        prev_prod = KB["products"].get(gen_meta[0], {}).get("name", gen_meta[0])
        curr_prod = KB["products"][product_id]["name"]
        st.warning(
            f"현재 검수 중인 글은 **{prev_prod} · {gen_meta[1]}** 기준입니다. "
            f"선택한 **{curr_prod} · {industry}** 기준으로 다시 생성할 수 있습니다."
        )
        if st.button("선택한 업종·제품으로 다시 생성"):
            _run_generate(API_KEY, MODEL, product_id, industry, install_type, tags, notes,
                          "선택한 업종·제품으로 다시 생성")
            c = st.session_state.get("content")
            gen_meta = st.session_state.get("generated_meta")

    check_product_id = gen_meta[0] if gen_meta else product_id
    allowed = factcheck.build_allowed(
        factcheck.sources_from_kb(KB, check_product_id) + [(st.session_state.get("notes", ""), "현장 확인(직원)")]
    )
    left, right = st.columns(2)  # 좁은 화면에서는 Streamlit이 위아래로 쌓는다
    blog = left.text_area(
        "블로그 글 (수정하면 검사가 바로 다시 돌아갑니다)",
        f"{c['blog']['title']}\n\n{c['blog']['body']}",
        height=300,
        key="blog_edit",
    )
    cards = right.text_area(
        "카드뉴스 5장 문구",
        utils.format_cards_text(c.get("cards", [])),
        height=300,
        key="cards_edit",
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
    st.caption("검증 범례: 초록색 = 근거 확인(마우스를 올리면 출처 표시) · 빨간색 = 확인 필요 또는 금지 표현")
    for label, text, found in results:
        n = sum(f.status != "ok" for f in found)
        st.subheader(f"{label}: 확인 필요 {n}건 · 근거 확인 {len(found) - n}건")
        st.markdown(factcheck.highlight(text, found), unsafe_allow_html=True)

    if c.get("used_claims"):
        st.caption("AI가 사용했다고 밝힌 근거: " + ", ".join(c["used_claims"]))

    st.subheader("수정본 복사 · 내려받기")
    export_md = utils.build_export_markdown(blog, cards)
    tab_blog, tab_cards, tab_all = st.tabs(["블로그 복사", "카드뉴스 복사", "전체(.md) 복사"])
    with tab_blog:
        st.code(blog, language="markdown")
    with tab_cards:
        st.code(cards, language="markdown")
    with tab_all:
        st.code(export_md, language="markdown")

    st.download_button(
        "검수본 내려받기 (.md)",
        export_md,
        file_name="t-ad_content.md",
        mime="text/markdown",
    )

stage = 4 if st.session_state.get("content") else 2 if st.session_state.get("analysis") else 1
steps_slot.markdown(ui.steps_html(stage), unsafe_allow_html=True)
