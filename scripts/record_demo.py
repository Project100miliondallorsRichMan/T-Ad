"""시연 시나리오를 자동으로 돌리며 녹화한다 (#10).

시나리오: 노출 확인 체크 → 사진 업로드 → 사진 분석 → 태그 확인 → 콘텐츠 생성
        → 근거 없는 수치를 넣으면 '확인 필요' 빨간 표시 → 지우면 사라짐

준비
  pip install playwright && python -m playwright install chromium
  streamlit run app.py   (다른 터미널에서, 키는 .streamlit/secrets.toml)

실행
  python scripts/record_demo.py [사진 경로 ...]

결과
  docs/demo.gif               README용 짧은 GIF
  demo_recording/*.webm       원본 영상(제출용 백업, 커밋하지 않음)
"""
import io
import os
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = os.environ.get("DEMO_URL", "http://localhost:8501")
PHOTOS = [Path(p) for p in sys.argv[1:]] or [ROOT / "sample_photos" / "01_스탠드형.jpg"]
GIF = Path(os.environ.get("DEMO_GIF", ROOT / "docs" / "demo.gif"))
VIDEO_DIR = ROOT / "demo_recording"
W, H = 1280, 800
GIF_W = 960
# 근거에 없는 수치. 팩트체크가 빨갛게 표시해야 한다.
INVENTED = "\n\n설치는 2시간이면 끝나고, 도입 후 악성 민원이 30% 줄었습니다."

frames: list[tuple[Image.Image, int]] = []


def snap(page, hold_ms=900):
    img = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    img = img.resize((GIF_W, int(img.height * GIF_W / img.width)), Image.LANCZOS)
    frames.append((img, hold_ms))


def idle(page, timeout=180):
    """Streamlit 재실행이 끝날 때까지 기다린다."""
    time.sleep(0.8)
    end = time.time() + timeout
    while time.time() < end:
        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
            return
        time.sleep(0.5)
    raise TimeoutError("앱 응답이 너무 늦습니다")


def wait_text(page, text, timeout=180):
    page.get_by_text(text, exact=False).first.wait_for(timeout=timeout * 1000)


def main():
    VIDEO_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": W, "height": H}, locale="ko-KR",
                                  record_video_dir=str(VIDEO_DIR), record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        page.goto(URL)
        wait_text(page, "1. 사진 업로드")
        idle(page)
        snap(page, 1500)

        # 1. 노출 확인 체크 → 업로드
        page.get_by_text("가려졌거나 없음을 확인했습니다").click()
        idle(page)
        snap(page)
        page.locator('input[type="file"]').set_input_files([str(x) for x in PHOTOS])
        idle(page)
        snap(page, 1200)

        # 2. 사진 분석
        page.get_by_role("button", name="사진 분석").click()
        time.sleep(1)
        snap(page, 700)
        wait_text(page, "2. 태그 확인")
        idle(page)
        page.get_by_text("2. 태그 확인").first.scroll_into_view_if_needed()
        page.mouse.wheel(0, -80)
        time.sleep(0.4)
        snap(page, 2200)

        # 3. 콘텐츠 생성
        page.get_by_role("button", name="콘텐츠 생성").click()
        time.sleep(1)
        snap(page, 700)
        wait_text(page, "3. 검수")
        idle(page)
        page.get_by_text("3. 검수").first.scroll_into_view_if_needed()
        time.sleep(0.4)
        snap(page, 2500)
        page.get_by_text("카드뉴스 미리보기").first.scroll_into_view_if_needed()
        time.sleep(0.4)
        snap(page, 2000)

        # 4. 근거 없는 수치를 넣으면 빨간 표시
        blog = page.get_by_label("블로그 글", exact=False)
        original = blog.input_value()
        page.get_by_text("3. 검수").first.scroll_into_view_if_needed()
        blog.click()
        blog.press("Control+End")
        blog.type(INVENTED, delay=25)
        snap(page, 600)
        blog.press("Control+Enter")
        idle(page)
        wait_text(page, "게시 전에 고쳐 주세요", timeout=30)
        page.get_by_text("3. 검수").first.scroll_into_view_if_needed()
        time.sleep(0.4)
        snap(page, 2500)
        # 빨간 표시가 붙은 문장이 화면 가운데 오게
        try:
            page.locator("sup", has_text="확인 필요").last.evaluate("e => e.scrollIntoView({block: 'center'})")
        except Exception:  # 못 찾아도 녹화는 계속한다(API 호출을 다시 쓰지 않도록)
            page.get_by_text("블로그: 확인 필요").first.scroll_into_view_if_needed()
        time.sleep(0.4)
        snap(page, 2800)

        # 5. 고치면 사라짐
        blog.fill(original)
        blog.press("Control+Enter")
        idle(page)
        page.get_by_text("3. 검수").first.scroll_into_view_if_needed()
        time.sleep(0.4)
        snap(page, 3000)

        video = page.video.path() if page.video else None
        ctx.close()
        browser.close()

    imgs = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT) for f, _ in frames]
    imgs[0].save(GIF, save_all=True, append_images=imgs[1:], duration=[d for _, d in frames],
                 loop=0, optimize=True)
    print(f"GIF: {GIF} ({GIF.stat().st_size // 1024} KB, {len(frames)} frames)")
    if video:
        print(f"video: {video}")


if __name__ == "__main__":
    main()
