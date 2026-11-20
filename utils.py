"""앱 실행 및 배포 안정화를 위한 유틸리티 (이미지 경량화·EXIF 보정, 비밀키 검증, 포맷팅)."""
import hashlib
import io
import json
from collections.abc import Mapping
from pathlib import Path

_PLACEHOLDERS = {"여기에_키", "YOUR_API_KEY", "PASTE_YOUR_KEY_HERE", ""}
_EXT_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def resolve_secret(secrets_obj: Mapping | None, env_obj: Mapping, name: str, default: str | None = None) -> str | None:
    """st.secrets 우선 조회 후 환경변수로 fallback. 공백/예시 플레이스홀더는 미설정으로 본다."""
    val: str | None = None
    if secrets_obj is not None:
        try:
            raw = secrets_obj[name]
            if isinstance(raw, str):
                val = raw.strip()
        except Exception:
            val = None
    if not val:
        raw_env = env_obj.get(name)
        val = raw_env.strip() if isinstance(raw_env, str) else None
    if not val or val in _PLACEHOLDERS:
        return default
    return val


def normalize_mime(mime_type: str | None, filename: str = "") -> str:
    m = (mime_type or "").strip().lower()
    if m == "image/jpg":
        return "image/jpeg"
    if m in ("image/jpeg", "image/png", "image/webp"):
        return m
    ext = Path(filename).suffix.lower()
    return _EXT_MIME.get(ext, "image/jpeg")


def prepare_image(raw_bytes: bytes, mime_type: str | None = None, filename: str = "", max_dim: int = 1600) -> tuple[bytes, str]:
    """모바일 현장 사진의 EXIF 회전을 보정하고, 큰 이미지는 긴 변 max_dim 이하로 줄인다."""
    mime = normalize_mime(mime_type, filename)
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return raw_bytes, mime

    try:
        with Image.open(io.BytesIO(raw_bytes)) as opened:
            img = ImageOps.exif_transpose(opened)
            w, h = img.size
            if max(w, h) <= max_dim and opened is img:
                return raw_bytes, mime

            if max(w, h) > max_dim:
                img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

            fmt = "JPEG" if mime == "image/jpeg" else ("WEBP" if mime == "image/webp" else "PNG")
            if fmt == "JPEG" and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            buf = io.BytesIO()
            save_kwargs = {"quality": 88, "optimize": True} if fmt in ("JPEG", "WEBP") else {"optimize": True}
            img.save(buf, format=fmt, **save_kwargs)
            return buf.getvalue(), mime
    except Exception:
        return raw_bytes, mime


def load_sample_case(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def format_cards_text(cards: list[dict]) -> str:
    return "\n\n".join(
        f"[{x.get('no')}장] {x.get('headline', '')}\n{x.get('text', '')}\n(사진: {x.get('photo', '')})"
        for x in cards
    )


def build_export_markdown(blog: str, cards: str) -> str:
    return f"# 블로그\n\n{blog}\n\n# 카드뉴스\n\n{cards}\n"


def photo_signature(files: list[tuple[str, bytes]]) -> str:
    """올라온 사진 묶음의 지문. 사진이 하나라도 바뀌면 값이 달라진다. 사진이 없으면 빈 문자열."""
    if not files:
        return ""
    h = hashlib.sha256()
    for name, data in files:
        h.update(name.encode("utf-8"))
        h.update(len(data).to_bytes(8, "big"))
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


_ERROR_HINTS = (
    (("api key not valid", "api_key_invalid", "permission_denied", "unauthenticated", "401", "403"),
     "API 키가 올바르지 않거나 권한이 없습니다. Secrets의 GEMINI_API_KEY를 확인해 주세요."),
    (("resource_exhausted", "quota", "rate limit", "429"),
     "요청 한도를 넘었습니다. 1분쯤 기다린 뒤 다시 시도해 주세요."),
    (("not_found", "is not found", "not supported", "404"),
     "모델을 찾지 못했습니다. Secrets의 GEMINI_MODEL을 지금 쓸 수 있는 모델로 바꿔 주세요."),
    (("unavailable", "overloaded", "503", "500", "internal"),
     "AI 서버가 잠시 바쁩니다. 잠시 후 다시 시도해 주세요."),
    (("timeout", "timed out", "deadline", "connection", "network"),
     "네트워크가 불안정합니다. 연결을 확인하고 다시 시도해 주세요."),
)


def error_hint(exc: Exception) -> str:
    """AI 호출 실패를 직원이 바로 할 수 있는 조치 한 문장으로 바꾼다."""
    if isinstance(exc, (json.JSONDecodeError, ValueError)) and "api key" not in str(exc).lower():
        return "AI 응답 형식이 잘못 왔습니다. 대부분 다시 시도하면 해결됩니다."
    msg = f"{type(exc).__name__} {exc}".lower()
    for needles, hint in _ERROR_HINTS:
        if any(n in msg for n in needles):
            return hint
    return "일시적인 오류일 수 있습니다. 다시 시도해도 계속되면 화면을 캡처해 팀에 공유해 주세요."
