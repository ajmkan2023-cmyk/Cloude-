"""الهوية البصرية لفيديو المولودة: اللوحة اللونية، الخطوط، مقاس الفيديو.

اللوحة مستوحاة من معنى الاسم — المِسْك: عاجيّ دافئ كورق قديم، ذهب هادئ
غير لامع، ووردي خافت. لا ألوان صارخة ولا تباين قاسٍ؛ كل شيء ناعم.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FONT_DIR = ROOT / "fonts"
REPO = ROOT.parent


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# ── اللوحة اللونية ────────────────────────────────────────────────────
_HEX = {
    "paper":      "#F7F1E7",   # عاجيّ دافئ — الخلفية الأساس
    "paper_warm": "#F0E4D2",   # ظلّ الورق
    "paper_cool": "#FBF7F1",   # أفتح نقطة في الإضاءة
    "ink":        "#3B2A2C",   # بنّي مائل للأرجواني — النص الرئيسي
    "ink_soft":   "#7A6560",   # نص ثانوي
    "ink_faint":  "#A89388",   # إسناد ومراجع
    "gold":       "#C3A05C",   # الذهب الأساس
    "gold_light": "#E9D5A6",   # أعلى تدرّج الذهب
    "gold_deep":  "#96723A",   # أسفل تدرّج الذهب
    "rose":       "#D9A9A2",   # وردي خافت
    "rose_deep":  "#B87F79",
    "sage":       "#A6B29C",   # لمسة خضراء للأوراق
}
PALETTE: dict[str, tuple[int, int, int]] = {k: _rgb(v) for k, v in _HEX.items()}


def color(name: str, alpha: int | None = None):
    """لون من اللوحة، مع شفافية اختيارية."""
    c = PALETTE[name]
    return c if alpha is None else (*c, alpha)


# ── مقاس الفيديو ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class Video:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    margin: int = 112          # الهامش الجانبي الآمن
    frame_inset: int = 64      # بُعد الإطار الزخرفي عن الحافة

    @property
    def size(self) -> tuple[int, int]:
        return self.width, self.height

    @property
    def center(self) -> tuple[int, int]:
        return self.width // 2, self.height // 2

    @property
    def content_width(self) -> int:
        return self.width - 2 * self.margin


VIDEO = Video()

PRESETS: dict[str, Video] = {
    "vertical": Video(1080, 1920, 30, 112, 64),          # ستوري / ريلز / واتساب
    "square":   Video(1080, 1080, 30, 104, 56),          # منشور مربّع
    "wide":     Video(1920, 1080, 30, 168, 60),          # عرض على شاشة
}


def use_preset(name: str) -> Video:
    """يبدّل مقاس الفيديو عالميًا قبل بناء المشاهد."""
    global VIDEO
    if name not in PRESETS:
        raise ValueError(f"مقاس غير معروف: {name} (المتاح: {', '.join(PRESETS)})")
    VIDEO = PRESETS[name]
    return VIDEO


# ── الخطوط ────────────────────────────────────────────────────────────
FONTS: dict[str, str] = {
    "naskh":      "Amiri-Regular.ttf",     # نسخ كلاسيكي — الآيات والأدعية
    "naskh_bold": "Amiri-Bold.ttf",
    "ruqaa":      "ArefRuqaa-Regular.ttf",  # رقعة خطّية — كشف الاسم
    "ruqaa_bold": "ArefRuqaa-Bold.ttf",
    "kufi":       "ReemKufi-Regular.ttf",   # كوفي معاصر — العناوين الصغيرة
    "kufi_bold":  "ReemKufi-SemiBold.ttf",
    "latin":      "Cormorant-Light.ttf",    # لاتيني رفيع — التاريخ والاسم
    "latin_md":   "Cormorant-Medium.ttf",
}

_SYSTEM_FALLBACK = (
    Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSansArabic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/freefont/FreeSerif.ttf"),
)


def font_path(role: str) -> Path:
    """مسار ملف الخط لدور معيّن، مع احتياط من خطوط النظام."""
    try:
        path = FONT_DIR / FONTS[role]
    except KeyError:
        raise KeyError(f"دور خط غير معروف: {role} (المتاح: {', '.join(FONTS)})") from None
    if path.exists():
        return path
    for candidate in _SYSTEM_FALLBACK:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"خط مفقود: {path} — شغّل misk/fetch_fonts.sh")
