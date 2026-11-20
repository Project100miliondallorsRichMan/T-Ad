"""시연용 화면 조각: 단계 표시, 팩트체크 배지, 카드뉴스 미리보기."""
import base64
import io
import re
from html import escape

from PIL import Image, ImageOps

import factcheck

CSS = """<style>
.tad-steps{display:flex;gap:8px;margin:4px 0 18px}
.tad-step{flex:1;padding:10px 12px;border-radius:10px;background:#f1f3f7;color:#8a8f99;font-size:15px}
.tad-step b{display:inline-block;width:22px;height:22px;line-height:22px;text-align:center;border-radius:50%;
  background:#d5d9e2;color:#fff;margin-right:8px;font-size:13px}
.tad-step.done{background:#e8eefc;color:#2f5bd3}
.tad-step.done b{background:#2f5bd3}
.tad-step.active{background:#2f5bd3;color:#fff;font-weight:700}
.tad-step.active b{background:#fff;color:#2f5bd3}
.tad-badge{padding:18px 22px;border-radius:14px;font-size:22px;font-weight:800;margin:6px 0 14px}
.tad-badge small{display:block;font-size:15px;font-weight:500;margin-top:4px}
.tad-badge.bad{background:#fde2e1;color:#b71c1c;border:2px solid #f5a3a0}
.tad-badge.ok{background:#e3f4e8;color:#1b5e20;border:2px solid #9fd5ae}
.tad-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:12px;margin:8px 0 20px}
.tad-card{position:relative;aspect-ratio:4/5;border-radius:14px;overflow:hidden;background:#2b2f3a center/cover no-repeat}
.tad-card::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.05) 30%,rgba(0,0,0,.82))}
.tad-card-no{position:absolute;top:10px;left:10px;z-index:2;background:rgba(0,0,0,.55);color:#fff;
  font-size:12px;padding:2px 8px;border-radius:10px}
.tad-card-body{position:absolute;left:12px;right:12px;bottom:12px;z-index:1;color:#fff}
.tad-card-h{font-size:17px;font-weight:800;line-height:1.35;margin-bottom:6px}
.tad-card-t{font-size:13px;line-height:1.5;opacity:.95}
.tad-card-h div,.tad-card-t div{line-height:inherit!important}
</style>"""

STEPS = ["사진 업로드", "태그 확인", "콘텐츠 생성", "검수"]


def steps_html(current: int) -> str:
    """current: 지금 진행 중인 단계(1부터). 앞 단계는 완료로 표시."""
    items = []
    for i, name in enumerate(STEPS, 1):
        cls = "done" if i < current else "active" if i == current else ""
        items.append(f'<div class="tad-step {cls}"><b>{i}</b>{name}</div>')
    return '<div class="tad-steps">' + "".join(items) + "</div>"


def badge_html(bad: int, ok: int) -> str:
    if bad:
        return (f'<div class="tad-badge bad">확인 필요 {bad}건 — 게시 전에 고쳐 주세요'
                f'<small>근거 확인 {ok}건 · 빨간 표시를 고치면 바로 다시 검사합니다</small></div>')
    return (f'<div class="tad-badge ok">확인 필요 0건 — 게시할 수 있습니다'
            f'<small>근거 확인 {ok}건 · 모든 수치·표현이 승인된 근거와 일치</small></div>')


def thumb_b64(data: bytes, size: int = 640) -> str:
    """카드 배경용 축소 JPEG. 휴대폰 사진의 회전 정보(EXIF)를 반영한다."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    img.thumbnail((size, size))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


_HEAD_RE = re.compile(r"\[(\d+)장\]\s*(.*)")
_PHOTO_RE = re.compile(r"\(사진:\s*(.*)\)\s*$")


def parse_cards(text: str) -> list[dict]:
    """검수 칸의 카드뉴스 문구('[n장] 제목 / 본문 / (사진: n)' 블록)를 다시 카드 목록으로."""
    cards = []
    for i, block in enumerate(b for b in re.split(r"\n\s*\n", text.strip()) if b.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        m = _HEAD_RE.match(lines[0])
        no, headline = (int(m.group(1)), m.group(2)) if m else (i + 1, lines[0])
        p = _PHOTO_RE.match(lines[-1]) if len(lines) > 1 else None
        body = lines[1:-1] if p else lines[1:]
        cards.append({"no": no, "headline": headline.strip(), "text": " ".join(body).strip(),
                      "photo": p.group(1).strip() if p else ""})
    return cards


def cards_html(cards: list[dict], thumbs: list[str], allowed: dict, banned: list[str]) -> str:
    """사진 위에 문구를 얹은 카드 미리보기. 문구에도 팩트체크 표시를 그대로 보여 준다."""
    def marked(t: str) -> str:
        return factcheck.highlight(t, factcheck.check(t, allowed, banned))

    out = []
    for i, c in enumerate(cards):
        m = re.search(r"\d+", c["photo"])
        idx = int(m.group()) - 1 if m else i
        bg = f' style="background-image:url(data:image/jpeg;base64,{thumbs[idx % len(thumbs)]})"' if thumbs else ""
        out.append(
            f'<div class="tad-card"{bg}><div class="tad-card-no">{escape(str(c["no"]))}/{len(cards)}</div>'
            f'<div class="tad-card-body"><div class="tad-card-h">{marked(c["headline"])}</div>'
            f'<div class="tad-card-t">{marked(c["text"])}</div></div></div>'
        )
    return '<div class="tad-cards">' + "".join(out) + "</div>"
